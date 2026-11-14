"""Per-frame processing: rectify -> field crops -> gates -> recognition -> format (SPEC 7.2, 11.2).

Milestone 1 scope: steps 1-4 of SPEC 11.2 (gates, reading, normalization, format validation).
Confirmation over time, plausibility and publishing come in Milestone 2; change detection
(read only changed crops) in Milestone 3. Every enabled field is read on every frame.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import numpy.typing as npt

from optima_time.config.models import Profile
from optima_time.fields.formats import ClockValue, NumberValue
from optima_time.geometry import Rectifier, crop
from optima_time.guard import GuardResult, GuardState, LayoutGuard
from optima_time.preprocess import contrast
from optima_time.recognizers.base import Crop, Reading, Recognizer
from optima_time.sources.base import Frame

Value = ClockValue | NumberValue


class ReadStatus(StrEnum):
    VALID = "valid"  # passed the gates and the format
    INVALID = "invalid"  # text doesn't fit the format
    LOW_CONFIDENCE = "low_confidence"
    BLANK = "blank"  # too little contrast, or nothing read


@dataclass
class FieldRead:
    field_id: str
    status: ReadStatus
    contrast: float
    reading: Reading | None = None  # None when the contrast gate skipped OCR
    value: Value | None = None
    text: str | None = None  # rendered output text (VALID only)
    crop: npt.NDArray[np.uint8] | None = None  # kept only with keep_crops


@dataclass
class FrameResult:
    seq: int
    pts: float | None
    arrived_ns: int
    done_ns: int
    fields: dict[str, FieldRead]
    timings_ms: dict[str, float] = field(default_factory=dict)
    guard: GuardResult = field(default_factory=lambda: GuardResult(GuardState.OFF))

    @property
    def latency_ms(self) -> float:
        return (self.done_ns - self.arrived_ns) / 1e6


RecognizerFactory = Callable[[str], Recognizer]


def default_factory(threads: int) -> RecognizerFactory:
    def make(model: str) -> Recognizer:
        from optima_time.recognizers.ppocr import PPOCRRecognizer

        return PPOCRRecognizer(model, threads=threads)

    return make


class Pipeline:
    def __init__(
        self,
        profile: Profile,
        recognizer_factory: RecognizerFactory | None = None,
        threads: int = 2,
        keep_crops: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._profile = profile
        self._factory = recognizer_factory or default_factory(threads)
        self._recognizers: dict[str, Recognizer] = {}
        self._rectifier: Rectifier | None = None
        self._last_valid: dict[str, Value] = {}
        self._guard = LayoutGuard(profile.guard)
        self.keep_crops = keep_crops
        self.last_rectified: npt.NDArray[np.uint8] | None = None

    @property
    def profile(self) -> Profile:
        with self._lock:
            return self._profile

    def update_profile(self, profile: Profile) -> None:
        """Swap the profile (e.g. after editing corners or fields in the UI)."""
        with self._lock:
            if profile.geometry != self._profile.geometry:
                self._rectifier = None
            if profile.guard != self._profile.guard:
                self._guard = LayoutGuard(profile.guard)
            self._profile = profile
            ids = {f.id for f in profile.fields}
            self._last_valid = {k: v for k, v in self._last_valid.items() if k in ids}

    def _recognizer(self, model: str) -> Recognizer:
        if model not in self._recognizers:
            self._recognizers[model] = self._factory(model)
        return self._recognizers[model]

    def rectifier_for(self, frame_size: tuple[int, int]) -> Rectifier:
        with self._lock:
            rect, geo = self._rectifier, self._profile.geometry
            if rect is None or rect.frame_size != frame_size:
                rect = Rectifier.create(geo.corners, frame_size, geo.rotate, geo.max_width)
                self._rectifier = rect
            return rect

    def process(self, frame: Frame) -> FrameResult:
        t0 = time.perf_counter_ns()
        profile = self.profile
        h, w = frame.image.shape[:2]
        rectified = self.rectifier_for((w, h)).warp(frame.image)
        self.last_rectified = rectified
        with self._lock:
            guard = self._guard.check(rectified)
        t_warp = time.perf_counter_ns()

        results: dict[str, FieldRead] = {}
        if not guard.ok:  # the board shows something else: read nothing (SPEC 9.4)
            done = time.perf_counter_ns()
            return FrameResult(
                frame.seq,
                frame.pts,
                frame.t_ns,
                time.monotonic_ns(),
                results,
                {"warp_guard": (t_warp - t0) / 1e6, "total": (done - t0) / 1e6},
                guard,
            )
        batches: dict[str, list[tuple[str, Crop]]] = {}
        fields = {f.id: f for f in profile.fields if f.enabled}
        for f in fields.values():
            image = crop(rectified, f.roi, f.margin)
            c = contrast(image)
            kept = image if self.keep_crops else None
            if c < f.min_contrast:  # gate: unlit / blown out / covered
                results[f.id] = FieldRead(f.id, ReadStatus.BLANK, c, crop=kept)
                continue
            results[f.id] = FieldRead(f.id, ReadStatus.BLANK, c, crop=kept)
            batches.setdefault(f.engine.model, []).append(
                (f.id, Crop(image, f.allowed_chars(), f.engine.min_width))
            )
        t_crop = time.perf_counter_ns()

        for model, items in batches.items():
            readings = self._recognizer(model).read([c for _, c in items])
            for (fid, _), reading in zip(items, readings, strict=True):
                f = fields[fid]
                r = results[fid]
                r.reading = reading
                if not reading.text:
                    r.status = ReadStatus.BLANK
                elif reading.confidence < f.min_confidence:
                    r.status = ReadStatus.LOW_CONFIDENCE
                elif (value := f.parse(reading.text, self._last_valid.get(fid))) is None:
                    r.status = ReadStatus.INVALID
                else:
                    r.status, r.value, r.text = ReadStatus.VALID, value, f.render(value)
                    self._last_valid[fid] = value
        t_ocr = time.perf_counter_ns()

        return FrameResult(
            seq=frame.seq,
            pts=frame.pts,
            arrived_ns=frame.t_ns,
            done_ns=time.monotonic_ns(),
            fields=results,
            guard=guard,
            timings_ms={
                "warp_guard": (t_warp - t0) / 1e6,
                "crop_gate": (t_crop - t_warp) / 1e6,
                "ocr": (t_ocr - t_crop) / 1e6,
                "total": (t_ocr - t0) / 1e6,
            },
        )
