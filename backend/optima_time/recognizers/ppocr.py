"""PP-OCRv6 text recognition on ONNX Runtime, CPU only (SPEC 10.2).

Adapted from ScoreSight (https://github.com/royshil/scoresight), MIT License,
Copyright (c) 2024 OCC AI: Open tools for Content Creators and Streamers. See THIRD_PARTY.md.
(resize_normalize, greedy CTC and the whitelist class grouping follow src/ppocr_engine.py.)

- No detection step: a field's crop already is one line of text.
- Input: the raw colour crop, resized to the model height (48) keeping its aspect ratio,
  scaled to [-1, 1], zero-padded on the right to at least min_width (DECISIONS D3, D9).
- Greedy CTC decoding limited to the field's characters: at each step the blank competes
  only with allowed characters; characters equal under NFKC count as one.
- Crops of the same padded width go through the model together, so a crop's reading never
  depends on the other fields in the frame.
- Few threads, spinning off: vMix runs on the same PC (DECISIONS D4).
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import onnxruntime as ort

from optima_time.recognizers.base import Crop, Reading

MODELS_ENV = "OPTIMA_TIME_MODELS"
MAX_BATCH = 32


def models_dir() -> Path:
    """models/ppocr: OPTIMA_TIME_MODELS, the PyInstaller bundle, or the repository."""
    if env := os.environ.get(MODELS_ENV):
        return Path(env)
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "models" / "ppocr"
    return Path(__file__).resolve().parents[3] / "models" / "ppocr"


def resize_normalize(image: npt.NDArray[np.uint8], height: int, width: int) -> np.ndarray:
    h, w = image.shape[:2]
    resized_w = max(1, min(width, math.ceil(height * w / max(1, h))))
    resized = cv2.resize(image, (resized_w, height)).astype(np.float32)
    resized = (resized.transpose(2, 0, 1) / 255.0 - 0.5) / 0.5
    padded = np.zeros((3, height, width), dtype=np.float32)
    padded[:, :, :resized_w] = resized
    return padded


def padded_width(h: int, w: int, height: int, min_width: int) -> int:
    return max(min_width, int(height * w / max(1, h)))


@dataclass(frozen=True)
class ClassGroups:
    labels: list[str]  # "" (blank), then one output string per group
    columns: npt.NDArray[np.intp]
    starts: npt.NDArray[np.intp]

    def reduce(self, probs: np.ndarray) -> np.ndarray:
        grouped = np.add.reduceat(probs[:, self.columns], self.starts, axis=1)
        return np.concatenate([probs[:, :1], grouped], axis=1)


def class_groups(characters: list[str], allowed: str) -> ClassGroups:
    groups: dict[str, list[int]] = {}
    for index, char in enumerate(characters):
        if index == 0:
            continue
        form = unicodedata.normalize("NFKC", char)
        if form and all(c in allowed for c in form):
            groups.setdefault(form, []).append(index)
    if not groups:
        raise ValueError(f"the model has none of the characters {allowed!r}")
    labels, columns, starts = [""], [], []
    for form, indices in groups.items():
        labels.append(form)
        starts.append(len(columns))
        columns.extend(indices)
    return ClassGroups(labels, np.array(columns, np.intp), np.array(starts, np.intp))


def ctc_greedy(probs: np.ndarray, labels: list[str]) -> tuple[str, list[float]]:
    """Best class per step, repeats merged, blanks (class 0) dropped."""
    best = probs.argmax(axis=1)
    keep = best != 0
    keep[1:] &= best[1:] != best[:-1]
    kept = best[keep]
    confs = probs[np.flatnonzero(keep), kept].astype(float).tolist()
    return "".join(labels[i] for i in kept), confs


def as_probabilities(output: np.ndarray) -> np.ndarray:
    """The exported models end with a softmax; apply one if a model doesn't."""
    if output.min() >= 0.0 and np.allclose(output.sum(axis=-1), 1.0, atol=1e-3):
        return output
    shifted = np.exp(output - output.max(axis=-1, keepdims=True))
    return shifted / shifted.sum(axis=-1, keepdims=True)


class PPOCRRecognizer:
    def __init__(self, model: str = "tiny", threads: int = 2, folder: Path | None = None):
        folder = folder or models_dir() / model
        onnx = folder / "inference.onnx"
        if not onnx.exists():
            raise FileNotFoundError(
                f"model {model!r} not found in {folder}; run: uv run python scripts/fetch_models.py"
            )
        config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        lines = (folder / "characters.txt").read_bytes().decode("utf-8").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        self.characters = ["", *lines, " "]  # blank, dictionary, space (use_space_char)
        self.height = int(config["image_height"])
        self.default_min_width = int(config["min_width"])
        self.rgb = str(config.get("channel_order", "BGR")).upper() == "RGB"
        self.name = f"ppocr-{model}"

        options = ort.SessionOptions()
        options.log_severity_level = 3
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        self.session = ort.InferenceSession(str(onnx), options, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        classes = self.session.get_outputs()[0].shape[-1]
        if isinstance(classes, int) and classes != len(self.characters):
            raise RuntimeError(
                f"model has {classes} classes, characters.txt {len(self.characters)}"
            )
        self._groups: dict[str, ClassGroups] = {}

    def _prepare(self, image: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)  # type: ignore[assignment]
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)  # type: ignore[assignment]
        if self.rgb:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  # type: ignore[assignment]
        return image

    def _decode(self, probs: np.ndarray, allowed: str | None) -> tuple[str, list[float]]:
        if not allowed:
            return ctc_greedy(probs, self.characters)
        groups = self._groups.get(allowed)
        if groups is None:
            groups = self._groups[allowed] = class_groups(self.characters, allowed)
        return ctc_greedy(groups.reduce(probs), groups.labels)

    def read(self, crops: list[Crop]) -> list[Reading]:
        results = [Reading("", 0.0, engine=self.name) for _ in crops]
        by_width: dict[int, list[int]] = {}
        images: dict[int, npt.NDArray[np.uint8]] = {}
        for i, crop in enumerate(crops):
            img = crop.image
            if img is None or img.ndim < 2 or img.shape[0] < 2 or img.shape[1] < 2:
                continue
            images[i] = self._prepare(img)
            min_w = crop.min_width or self.default_min_width
            width = padded_width(img.shape[0], img.shape[1], self.height, min_w)
            by_width.setdefault(width, []).append(i)
        for width in sorted(by_width):
            indices = by_width[width]
            for start in range(0, len(indices), MAX_BATCH):
                chunk = indices[start : start + MAX_BATCH]
                t0 = time.perf_counter_ns()
                batch = np.stack([resize_normalize(images[i], self.height, width) for i in chunk])
                [out] = self.session.run(None, {self.input_name: batch})
                probs = as_probabilities(np.asarray(out, dtype=np.float32))
                elapsed = (time.perf_counter_ns() - t0) / 1e6
                for row, i in enumerate(chunk):
                    text, confs = self._decode(probs[row], crops[i].allowed)
                    text = unicodedata.normalize("NFKC", text)
                    conf = float(np.mean(confs)) if confs else 0.0
                    results[i] = Reading(text, conf, confs, self.name, elapsed)
        return results
