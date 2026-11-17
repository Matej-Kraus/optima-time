"""Rectification of the board from 4 corners and cutting field crops (SPEC 9.1).

Coordinates in the profile are relative (0-1): corners relative to the source frame, ROIs
relative to the rectified board. That way a profile survives a change of source resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

from optima_time.fields.models import Roi

Image = npt.NDArray[np.uint8]
Point = tuple[float, float]


def rectified_size(
    corners_px: npt.NDArray[np.float64], max_width: int, aspect: float = 0.0
) -> tuple[int, int]:
    """Width and height of the rectified board (before rotation): mean opposite edge lengths,
    scaled down to max_width, never up (upscaling adds no detail).

    aspect > 0 (the real board's width / height) corrects a board seen at an angle: from the
    side it looks narrower than it is, and the digits would come out squeezed. The longer side
    is kept and the other one is set from the aspect, so nothing loses resolution."""
    tl, tr, br, bl = corners_px
    width = float(np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    height = float(np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    if width < 2 or height < 2:
        raise ValueError("corners are too close together")
    if aspect > 0:
        if width / height < aspect:
            width = height * aspect
        else:
            height = width / aspect
    scale = min(1.0, max_width / width)
    return max(2, round(width * scale)), max(2, round(height * scale))


def _rotate_points(points: npt.NDArray[np.float64], w: int, h: int, rotate: int):
    """Where points of a w x h image end up after rotating it clockwise by `rotate` degrees."""
    x, y = points[:, 0], points[:, 1]
    match rotate:
        case 0:
            return points, (w, h)
        case 90:
            return np.stack([h - y, x], axis=1), (h, w)
        case 180:
            return np.stack([w - x, h - y], axis=1), (w, h)
        case 270:
            return np.stack([y, w - x], axis=1), (h, w)
    raise ValueError(f"rotate must be 0, 90, 180 or 270, not {rotate}")


@dataclass(frozen=True)
class Rectifier:
    """Maps a source frame of a given size to the rectified board image."""

    matrix: npt.NDArray[np.float64]  # source px -> rectified px
    size: tuple[int, int]  # rectified (width, height)
    frame_size: tuple[int, int]  # source (width, height)

    @classmethod
    def create(
        cls,
        corners_rel: list[Point] | list[tuple[float, float]],
        frame_size: tuple[int, int],
        rotate: int = 0,
        max_width: int = 1280,
        aspect: float = 0.0,
    ) -> Rectifier:
        fw, fh = frame_size
        src = np.array([(x * fw, y * fh) for x, y in corners_rel], dtype=np.float64)
        w, h = rectified_size(src, max_width if rotate in (0, 180) else 10**9, aspect)
        dst = np.array([(0, 0), (w, 0), (w, h), (0, h)], dtype=np.float64)
        dst, (rw, rh) = _rotate_points(dst, w, h, rotate)
        if rotate in (90, 270) and rw > max_width:  # limit the final width
            s = max_width / rw
            dst, rw, rh = dst * s, max(2, round(rw * s)), max(2, round(rh * s))
        matrix = cv2.getPerspectiveTransform(src.astype(np.float32), dst.astype(np.float32))
        return cls(matrix.astype(np.float64), (rw, rh), (fw, fh))

    def warp(self, frame: Image) -> Image:
        h, w = frame.shape[:2]
        if (w, h) != self.frame_size:
            raise ValueError(f"frame is {w}x{h}, rectifier was made for {self.frame_size}")
        return cv2.warpPerspective(  # type: ignore[return-value]
            frame, self.matrix, self.size, flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0)
        )

    def to_rectified(self, points_src_rel: list[Point]) -> list[Point]:
        """Source-relative points -> rectified-relative points."""
        return self._map(points_src_rel, self.frame_size, self.matrix, self.size)

    def to_source(self, points_rect_rel: list[Point]) -> list[Point]:
        """Rectified-relative points -> source-relative points (for drawing overlays)."""
        return self._map(points_rect_rel, self.size, np.linalg.inv(self.matrix), self.frame_size)

    @staticmethod
    def _map(points, from_size, matrix, to_size) -> list[Point]:
        fw, fh = from_size
        tw, th = to_size
        pts = np.array([[(x * fw, y * fh)] for x, y in points], dtype=np.float64)
        out = cv2.perspectiveTransform(pts, matrix)[:, 0, :]
        return [(float(x / tw), float(y / th)) for x, y in out]


def roi_box(roi: Roi, size: tuple[int, int], margin: float) -> tuple[int, int, int, int]:
    """Pixel box (x0, y0, x1, y1) of a ROI in an image of `size`, grown by margin x ROI height
    on every side and clamped to the image."""
    w, h = size
    m = margin * roi.h * h
    x0 = max(0, round(roi.x * w - m))
    y0 = max(0, round(roi.y * h - m))
    x1 = min(w, round((roi.x + roi.w) * w + m))
    y1 = min(h, round((roi.y + roi.h) * h + m))
    return x0, y0, max(x0 + 1, x1), max(y0 + 1, y1)


def crop(image: Image, roi: Roi, margin: float = 0.0) -> Image:
    h, w = image.shape[:2]
    x0, y0, x1, y1 = roi_box(roi, (w, h), margin)
    return image[y0:y1, x0:x1].copy()
