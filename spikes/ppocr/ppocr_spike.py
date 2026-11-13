"""Spike A: how well and how fast PP-OCRv6 rec reads scoreboard crops.

One-off experiment (Milestone 0), not product code.

Adapted from ScoreSight (https://github.com/royshil/scoresight), MIT License,
Copyright (c) 2024 OCC AI: Open tools for Content Creators and Streamers. See THIRD_PARTY.md.
(resize_normalize, ctc_greedy and the whitelist grouping follow src/ppocr_engine.py.)

Crops come from:
  --synthetic N   rendered LED-wall crops (green clock, cyan score, white period ...)
  --samples FILE  real photos with hand-drawn boxes (format: see README.md)

Usage:
  uv run python spikes/ppocr/ppocr_spike.py --synthetic 400
  uv run python spikes/ppocr/ppocr_spike.py --samples samples/crops.json
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import random
import statistics
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import yaml
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
MODELS_DIR = HERE / "models"
OUT_DIR = HERE / "out"

WHITELISTS = {
    "clock": "0123456789:.",
    "number": "0123456789",
    "period": "0123456789",
}

# --- recognizer ----------------------------------------------------------------


@dataclass
class Groups:
    labels: list[str]
    columns: np.ndarray
    starts: np.ndarray

    def reduce(self, probs: np.ndarray) -> np.ndarray:
        grouped = np.add.reduceat(probs[:, self.columns], self.starts, axis=1)
        return np.concatenate([probs[:, :1], grouped], axis=1)


def class_groups(characters: list[str], allowed: str) -> Groups:
    groups: dict[str, list[int]] = {}
    for index, char in enumerate(characters):
        if index == 0:
            continue
        form = unicodedata.normalize("NFKC", char)
        if form and all(c in allowed for c in form):
            groups.setdefault(form, []).append(index)
    labels = [""]
    columns: list[int] = []
    starts: list[int] = []
    for form, indices in groups.items():
        labels.append(form)
        starts.append(len(columns))
        columns.extend(indices)
    return Groups(labels, np.array(columns), np.array(starts))


def ctc_greedy(probs: np.ndarray, labels: list[str]) -> tuple[str, float]:
    best = probs.argmax(axis=1)
    keep = best != 0
    keep[1:] &= best[1:] != best[:-1]
    kept = best[keep]
    if kept.size == 0:
        return "", 0.0
    conf = float(probs[np.flatnonzero(keep), kept].mean())
    return "".join(labels[i] for i in kept), conf


def resize_normalize(image: np.ndarray, height: int, width: int) -> np.ndarray:
    h, w = image.shape[:2]
    resized_w = max(1, min(width, math.ceil(height * w / max(1, h))))
    resized = cv2.resize(image, (resized_w, height)).astype(np.float32)
    resized = (resized.transpose(2, 0, 1) / 255.0 - 0.5) / 0.5
    padded = np.zeros((3, height, width), dtype=np.float32)
    padded[:, :, :resized_w] = resized
    return padded


class Recognizer:
    def __init__(self, name: str, threads: int, min_width: int | None = None):
        folder = MODELS_DIR / name
        with (folder / "inference.yml").open(encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.characters = ["", *config["PostProcess"]["character_dict"], " "]
        shape = [3, 48, 320]
        for op in config["PreProcess"]["transform_ops"]:
            if "RecResizeImg" in op:
                shape = op["RecResizeImg"]["image_shape"]
        self.height, self.min_width = int(shape[1]), min_width or int(shape[2])
        options = ort.SessionOptions()
        options.log_severity_level = 3
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        self.session = ort.InferenceSession(
            str(folder / "inference.onnx"), options, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self._groups: dict[str, Groups] = {}

    def width_for(self, crop: np.ndarray) -> int:
        h, w = crop.shape[:2]
        return max(self.min_width, int(self.height * w / max(1, h)))

    def run(self, crops: list[np.ndarray]) -> np.ndarray:
        width = max(self.width_for(c) for c in crops)
        batch = np.stack([resize_normalize(c, self.height, width) for c in crops])
        [out] = self.session.run(None, {self.input_name: batch})
        return np.asarray(out, dtype=np.float32)

    def decode(self, probs: np.ndarray, allowed: str | None) -> tuple[str, float]:
        if not allowed:
            return ctc_greedy(probs, self.characters)
        groups = self._groups.get(allowed)
        if groups is None:
            groups = self._groups[allowed] = class_groups(self.characters, allowed)
        return ctc_greedy(groups.reduce(probs), groups.labels)


# --- crops -----------------------------------------------------------------------


@dataclass
class Crop:
    image: np.ndarray  # BGR
    kind: str  # clock | number | period
    truth: str  # "" = unlit / blank
    tag: str  # sub-group for the report


FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("no TrueType font found; add one to FONT_CANDIDATES")


def render_led(text: str, color_bgr: tuple[int, int, int], rng: random.Random) -> np.ndarray:
    """Text drawn on a coarse LED grid, each LED a round dot, as a camera sees a video wall."""
    rows = rng.randint(12, 22)  # LEDs per character height
    font = load_font(int(rows * 1.35))
    pad = 2
    probe = Image.new("L", (1, 1))
    box = ImageDraw.Draw(probe).textbbox((0, 0), text or "88:88", font=font)
    w, h = box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad
    grid = Image.new("L", (w, h), 0)
    if text:
        ImageDraw.Draw(grid).text((pad - box[0], pad - box[1]), text, fill=255, font=font)
    leds = np.asarray(grid, dtype=np.float32) / 255.0

    pitch = rng.randint(5, 8)
    dot = rng.uniform(0.55, 0.85) * pitch
    yy, xx = np.mgrid[0:pitch, 0:pitch]
    c = (pitch - 1) / 2
    mask = (((yy - c) ** 2 + (xx - c) ** 2) <= (dot / 2) ** 2).astype(np.float32)
    up = np.kron(leds, mask)
    unlit = rng.uniform(0.02, 0.10)  # dark LEDs still reflect a bit
    up = np.maximum(up, np.kron(np.ones_like(leds), mask) * unlit)
    image = np.stack([up * ch for ch in color_bgr], axis=2)
    return np.clip(image, 0, 255).astype(np.uint8)


def camera(image: np.ndarray, rng: random.Random, hard: bool = False) -> np.ndarray:
    """Perspective, scale to a camera-sized crop, blur, exposure, noise, JPEG.

    hard: small fields, blown-out LEDs, heavier blur (a far or badly exposed camera)."""
    h, w = image.shape[:2]
    j = 0.04
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[x + rng.uniform(-j, j) * w, y + rng.uniform(-j, j) * h] for x, y in src])
    m = cv2.getPerspectiveTransform(src, dst)
    image = cv2.warpPerspective(image, m, (w, h), borderValue=(0, 0, 0))
    target_h = rng.randint(14, 30) if hard else rng.randint(24, 90)  # field height in camera pixels
    scale = target_h / h
    image = cv2.resize(image, (max(8, int(w * scale)), target_h), interpolation=cv2.INTER_AREA)
    if hard or rng.random() < 0.7:
        k = rng.choice([3, 5])
        image = cv2.GaussianBlur(image, (k, k), rng.uniform(0.3, 2.0 if hard else 1.2))
    gain = (
        rng.uniform(0.4, 2.8) if hard else rng.uniform(0.6, 1.5)
    )  # under/over exposure (over clips: blown LEDs)
    image = image.astype(np.float32) * gain + rng.uniform(0, 25)
    image += np.random.default_rng(rng.randint(0, 1 << 30)).normal(
        0, rng.uniform(2, 9), image.shape
    )
    image = np.clip(image, 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(60, 95)])
    assert ok
    image = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    margin = max(2, target_h // 6)  # a box drawn with some room around the text
    return cv2.copyMakeBorder(image, margin, margin, margin, margin, cv2.BORDER_REPLICATE)


GREEN, CYAN, WHITE, YELLOW, RED = (
    (40, 255, 40),
    (255, 230, 20),
    (240, 240, 240),
    (30, 220, 255),
    (40, 40, 255),
)


def synthetic(n: int, seed: int, hard: bool = False) -> list[Crop]:
    rng = random.Random(seed)
    makers = [
        (
            "clock",
            "clock mm:ss",
            GREEN,
            lambda: f"{rng.randint(0, 25):02d}:{rng.randint(0, 59):02d}",
        ),
        ("clock", "clock ss.d", GREEN, lambda: f"{rng.randint(0, 59)}.{rng.randint(0, 9)}"),
        (
            "clock",
            "penalty",
            rng.choice([YELLOW, WHITE, RED]),
            lambda: rng.choice(
                [
                    f"{rng.randint(0, 4)}:{rng.randint(0, 59):02d}",
                    f"{rng.randint(0, 4):02d}:{rng.randint(0, 59):02d}",
                ]
            ),
        ),
        ("number", "score 1 digit", CYAN, lambda: str(rng.randint(0, 9))),
        ("number", "score 2 digits", CYAN, lambda: str(rng.randint(10, 19))),
        ("period", "period", WHITE, lambda: str(rng.randint(1, 4))),
    ]
    crops = []
    for i in range(n):
        kind, tag, color, value = makers[i % len(makers)]
        truth = value()
        crops.append(Crop(camera(render_led(truth, color, rng), rng, hard), kind, truth, tag))
    # Unlit fields: only dark LEDs. Must not be read as digits (contrast gate needed?).
    for i in range(max(6, n // 20)):
        kind, tag, color, _ = makers[i % len(makers)]
        crops.append(Crop(camera(render_led("", color, rng), rng, hard), kind, "", "unlit"))
    return crops


def from_samples(path: Path) -> list[Crop]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    crops = []
    for entry in spec:
        image = cv2.imread(str(path.parent / entry["image"]), cv2.IMREAD_COLOR)
        if image is None:
            raise SystemExit(f"can't read {entry['image']}")
        for field in entry["fields"]:
            x, y, w, h = field["rect"]
            crop = image[y : y + h, x : x + w]
            crops.append(Crop(crop, field["type"], field["truth"], field.get("tag", field["type"])))
    return crops


# --- measurement -------------------------------------------------------------------


def evaluate(crops: list[Crop], model: str, threads: int, min_width: int | None) -> dict:
    rec = Recognizer(model, threads, min_width)
    for _ in range(3):
        rec.run([crops[0].image])  # warm-up
    results = {
        "model": model,
        "threads": threads,
        "min_width": rec.min_width,
        "by_tag": {},
        "errors": [],
    }
    single_ms: list[float] = []
    for crop in crops:
        t0 = time.perf_counter_ns()
        probs = rec.run([crop.image])[0]
        single_ms.append((time.perf_counter_ns() - t0) / 1e6)
        for wl in (False, True):
            text, conf = rec.decode(probs, WHITELISTS[crop.kind] if wl else None)
            text = unicodedata.normalize("NFKC", text).replace(" ", "")
            key = "wl" if wl else "raw"
            tag = results["by_tag"].setdefault(
                crop.tag, {"n": 0, "raw": 0, "wl": 0, "wl_conf_wrong": []}
            )
            if wl:
                tag["n"] += 1
            ok = text == crop.truth
            tag[key] += ok
            if wl and not ok:
                tag["wl_conf_wrong"].append(round(conf, 3))
                results["errors"].append(
                    {"tag": crop.tag, "truth": crop.truth, "read": text, "conf": round(conf, 3)}
                )
    # A whole frame: 8 fields (Time, 4 penalties, 2 scores, period) in one batch.
    frame = [c.image for c in crops[:8]]
    batch_ms = []
    for _ in range(30):
        t0 = time.perf_counter_ns()
        rec.run(frame)
        batch_ms.append((time.perf_counter_ns() - t0) / 1e6)
    results["ms_per_crop_median"] = round(statistics.median(single_ms), 2)
    results["ms_per_crop_p95"] = round(sorted(single_ms)[int(0.95 * len(single_ms))], 2)
    results["ms_frame8_median"] = round(statistics.median(batch_ms), 2)
    return results


def contact_sheet(crops: list[Crop], path: Path, limit: int = 48) -> None:
    rows = []
    for crop in crops[:limit]:
        img = cv2.resize(crop.image, (int(crop.image.shape[1] * 60 / crop.image.shape[0]), 60))
        canvas = np.zeros((60, 320, 3), np.uint8)
        canvas[:, : min(320, img.shape[1])] = img[:, :320]
        rows.append(canvas)
    cols = 3
    while len(rows) % cols:
        rows.append(np.zeros((60, 320, 3), np.uint8))
    grid = np.vstack([np.hstack(rows[i : i + cols]) for i in range(0, len(rows), cols)])
    cv2.imwrite(str(path), grid)


def print_accuracy(r: dict) -> None:
    print(f"{'group':16} {'n':>4} {'raw %':>7} {'wl %':>7}  conf of wrong wl readings")
    for tag, t in r["by_tag"].items():
        print(
            f"{tag:16} {t['n']:4} {100 * t['raw'] / t['n']:7.1f} {100 * t['wl'] / t['n']:7.1f}  "
            f"{sorted(t['wl_conf_wrong'])[-5:]}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", type=int, default=0)
    parser.add_argument("--samples", type=Path)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--threads", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--models", nargs="+", default=["tiny", "small"])
    parser.add_argument("--hard", action="store_true", help="harder synthetic crops")
    parser.add_argument("--min-width", type=int, nargs="+", default=[320])
    args = parser.parse_args()

    crops = (
        from_samples(args.samples)
        if args.samples
        else synthetic(args.synthetic or 300, args.seed, args.hard)
    )
    OUT_DIR.mkdir(exist_ok=True)
    source = "samples" if args.samples else f"synthetic{len(crops)}{'_hard' if args.hard else ''}"
    contact_sheet(crops, OUT_DIR / f"{source}_sheet.png")

    report = {
        "source": source,
        "machine": f"{platform.system()} {platform.machine()} {platform.processor()}",
        "onnxruntime": ort.__version__,
        "runs": [],
    }
    for model in args.models:
        for min_width in args.min_width:
            for threads in args.threads:
                r = evaluate(crops, model, threads, min_width)
                report["runs"].append(r)
                print(
                    f"\n== {model}, min width {min_width}, {threads} thread(s): "
                    f"{r['ms_per_crop_median']} ms/crop (p95 {r['ms_per_crop_p95']}), "
                    f"frame of 8 in one batch {r['ms_frame8_median']} ms"
                )
                if threads != args.threads[0]:
                    continue  # accuracy doesn't depend on threads
                print_accuracy(r)
    out = OUT_DIR / f"{source}_report.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
