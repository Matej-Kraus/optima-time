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
    """Gray as the max of B, G, R. Luma under-weights red and blue LEDs; the max doesn't."""
    if image.ndim == 2:
        return image
    return image.max(axis=2)


def contrast(image: Image) -> float:
    """Spread between the lit and the dark part of a crop: 99th - 10th percentile of
    max-channel gray (0-255). An unlit board, dark LEDs or a blown-out crop score low."""
    h, w = image.shape[:2]
    k = math.ceil(max(h, w) / CONTRAST_MAX_SIDE)
    if k > 1 and h >= k and w >= k:
        # Shrink first by a whole factor (box average): OpenCV's fast path, ~6x quicker than a
        # fractional INTER_AREA, and averaging never misses LED dots like subsampling could.
        hh, ww = h // k * k, w // k * k
        small = cv2.resize(image[:hh, :ww], (ww // k, hh // k), interpolation=cv2.INTER_AREA)
        image = np.asarray(small, np.uint8)
    gray = gray_max(image).ravel()
    lo_i, hi_i = int(0.10 * (gray.size - 1)), int(0.99 * (gray.size - 1))
    part = np.partition(gray, (lo_i, hi_i))
    return float(int(part[hi_i]) - int(part[lo_i]))


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
