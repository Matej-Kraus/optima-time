"""Image helpers: LED-friendly gray, the contrast gate, deinterlacing (SPEC 8, 9.2, 9.3).

PP-OCR gets the raw colour crop; these are for the gates (and later the preview and guard).
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import numpy.typing as npt

from optima_time.config.models import BlendMode, Deinterlace, ImageConfig

Image = npt.NDArray[np.uint8]

CONTRAST_MAX_SIDE = 64  # the gate works on a downscaled crop: cheap and noise-tolerant


def gray_max(image: Image) -> Image:
    """Gray as the max of B, G, R. Luma under-weights red and blue LEDs; the max doesn't.
    (OpenCV's per-element max is ~10x faster than numpy's max over the channel axis.)"""
    if image.ndim == 2:
        return image
    b, g, r = cv2.split(image)
    return np.asarray(cv2.max(cv2.max(b, g), r), np.uint8)


def shrink(image: Image, factor: int) -> Image:
    """Shrink by a whole factor with box averaging (OpenCV's fast INTER_AREA path)."""
    if factor <= 1:
        return image
    h, w = image.shape[:2]
    if h < factor or w < factor:
        return image
    hh, ww = h // factor * factor, w // factor * factor
    small = cv2.resize(image[:hh, :ww], (ww // factor, hh // factor), interpolation=cv2.INTER_AREA)
    return np.asarray(small, np.uint8)


def contrast(image: Image) -> float:
    """Spread between the lit and the dark part of a crop: 99th - 10th percentile of
    max-channel gray (0-255). An unlit board, dark LEDs or a blown-out crop score low."""
    h, w = image.shape[:2]
    # Shrink first by a whole factor (box average): OpenCV's fast path, ~6x quicker than a
    # fractional INTER_AREA, and averaging never misses LED dots like subsampling could.
    image = shrink(image, math.ceil(max(h, w) / CONTRAST_MAX_SIDE))
    gray = gray_max(image).ravel()
    lo_i, hi_i = int(0.10 * (gray.size - 1)), int(0.99 * (gray.size - 1))
    part = np.partition(gray, (lo_i, hi_i))
    return float(int(part[hi_i]) - int(part[lo_i]))


SIGNATURE_HEIGHT = 24


def signature(image: Image) -> npt.NDArray[np.float32]:
    """A small, normalized picture of a crop for change detection (SPEC 10.5): max-channel gray,
    shrunk by a whole factor to ~24 px high, blurred, then mean/std normalized so that LED
    flicker and exposure changes (gain) don't count as a change."""
    gray = gray_max(shrink(image, image.shape[0] // SIGNATURE_HEIGHT))  # shrink first: cheap
    g = np.asarray(cv2.GaussianBlur(np.asarray(gray, np.float32), (3, 3), 0), np.float32)
    return (g - g.mean()) / (g.std() + 8.0)


def difference(a: npt.NDArray[np.float32], b: npt.NDArray[np.float32]) -> float:
    """How much two signatures differ where they differ most: the mean absolute difference in
    the worst vertical band about one character wide. A single changed digit stands out; a global
    brightness flicker doesn't (DECISIONS D22)."""
    if a.shape != b.shape:
        return float("inf")
    cols = np.abs(a - b).mean(axis=0)
    band = max(2, a.shape[0] // 2)
    if cols.size <= band:
        return float(cols.mean())
    return float(np.convolve(cols, np.ones(band) / band, mode="valid").max())


def deinterlace(frame: Image, mode: Deinterlace) -> Image:
    """Remove combing from a woven interlaced frame (1080i): digits that change between the two
    fields would otherwise look torn."""
    if mode is Deinterlace.NONE:
        return frame
    if mode is Deinterlace.BLEND:
        out = frame.copy()
        out[:-1] = ((frame[:-1].astype(np.uint16) + frame[1:]) // 2).astype(np.uint8)
        return out
    # BOB: keep the even field, stretch it back to full height
    h, w = frame.shape[:2]
    return cv2.resize(frame[::2], (w, h), interpolation=cv2.INTER_LINEAR)  # type: ignore[return-value]


class FrameBlender:
    """Combines the last N rectified frames pixel by pixel (max or mean), SPEC 9.2."""

    def __init__(self, frames: int, mode: BlendMode) -> None:
        self.frames, self.mode = frames, mode
        self._recent: list[Image] = []

    def __call__(self, image: Image) -> Image:
        if self.frames <= 1:
            return image
        if self._recent and self._recent[-1].shape != image.shape:
            self._recent.clear()  # the geometry changed
        self._recent = [*self._recent[-(self.frames - 1) :], image]
        if len(self._recent) == 1:
            return image
        if self.mode is BlendMode.MAX:
            out = self._recent[0]
            for img in self._recent[1:]:
                out = cv2.max(out, img)
            return np.asarray(out, np.uint8)
        acc = np.zeros(image.shape, np.float32)
        for img in self._recent:
            acc += img
        return np.asarray(acc / len(self._recent) + 0.5, np.uint8)


def adjust_lut(cfg: ImageConfig) -> npt.NDArray[np.uint8]:
    """One 256-entry table for gamma, contrast (around mid-gray), brightness and invert."""
    v = np.arange(256, dtype=np.float64) / 255.0
    v = np.power(v, 1.0 / cfg.gamma)
    v = (v - 0.5) * cfg.contrast + 0.5 + cfg.brightness / 200.0
    v = np.clip(v, 0.0, 1.0)
    if cfg.invert:
        v = 1.0 - v
    return np.round(v * 255.0).astype(np.uint8)


class ImageAdjust:
    """Applies ImageConfig to the rectified board. Neutral settings return the image untouched
    (no copy, no cost)."""

    def __init__(self, cfg: ImageConfig) -> None:
        self.cfg = cfg
        self.neutral = cfg.neutral()
        self._lut = adjust_lut(cfg)
        self._lut_identity = bool(np.array_equal(self._lut, np.arange(256, dtype=np.uint8)))
        n = cfg.net_removal
        self._kernel = (
            cv2.getStructuringElement(cv2.MORPH_RECT, (2 * n + 1, 2 * n + 1)) if n else None
        )

    def __call__(self, image: Image) -> Image:
        if self.neutral:
            return image
        out = image
        if self._kernel is not None:  # closing: thin dark lines (a net) over bright digits vanish
            out = np.asarray(cv2.morphologyEx(out, cv2.MORPH_CLOSE, self._kernel), np.uint8)
        if not self._lut_identity:
            out = np.asarray(cv2.LUT(out, self._lut), np.uint8)
        if self.cfg.sharpen > 0:
            blur = cv2.GaussianBlur(out, (0, 0), 1.5)
            a = self.cfg.sharpen
            out = np.asarray(cv2.addWeighted(out, 1.0 + a, blur, -a, 0), np.uint8)
        return out
