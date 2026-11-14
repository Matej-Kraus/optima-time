"""Image helpers: LED-friendly gray, the contrast gate, deinterlacing (SPEC 8, 9.2, 9.3).

PP-OCR gets the raw colour crop; these are for the gates (and later the preview and guard).
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import numpy.typing as npt

from optima_time.config.models import Deinterlace

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
