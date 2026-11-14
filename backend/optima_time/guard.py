"""Layout guard: is the board showing the score layout right now? (SPEC 9.4)

The operator marks 1-3 anchors: static parts of the layout (e.g. the "PERIÓDA" caption). Their
look is stored in the profile as a small gray template. Every frame each anchor's area (with a
little room to search, for vibration) is compared with its template by normalized correlation,
which ignores brightness and contrast changes. If any anchor doesn't match, the frame counts as
"the board doesn't show the score": no field is read and published values are held. Reading
resumes only after recover_frames matching frames in a row.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from enum import StrEnum

import cv2
import numpy as np
import numpy.typing as npt

from optima_time.config.models import GuardConfig
from optima_time.fields.models import Roi
from optima_time.geometry import roi_box
from optima_time.preprocess import gray_max

Image = npt.NDArray[np.uint8]
TEMPLATE_WIDTH = 64
MIN_TEMPLATE_STD = 8.0  # a flat area can't tell layouts apart


class GuardState(StrEnum):
    OFF = "off"  # no anchors
    OK = "ok"
    LOST = "lost"  # the board shows something else
    RECOVERING = "recovering"  # anchors match again, waiting for recover_frames


@dataclass
class GuardResult:
    state: GuardState
    scores: list[float] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.state in (GuardState.OK, GuardState.OFF)


def _scale_for(roi: Roi, size: tuple[int, int]) -> float:
    w = max(1.0, roi.w * size[0])
    return TEMPLATE_WIDTH / w


def _prepare(image: Image, scale: float) -> Image:
    h, w = image.shape[:2]
    size = (max(4, round(w * scale)), max(4, round(h * scale)))
    small = gray_max(np.asarray(cv2.resize(image, size, interpolation=cv2.INTER_AREA), np.uint8))
    return np.asarray(cv2.GaussianBlur(small, (3, 3), 0), np.uint8)


def capture_template(rectified: Image, roi: Roi) -> str:
    """The anchor's template from the current rectified frame, as base64 PNG for the profile."""
    h, w = rectified.shape[:2]
    x0, y0, x1, y1 = roi_box(roi, (w, h), 0.0)
    template = _prepare(rectified[y0:y1, x0:x1], _scale_for(roi, (w, h)))
    if float(template.std()) < MIN_TEMPLATE_STD:
        raise ValueError("anchor area is flat (no text or edges): pick a caption or a logo")
    ok, data = cv2.imencode(".png", template)
    if not ok:
        raise ValueError("can't encode template")
    return base64.b64encode(data.tobytes()).decode("ascii")


def decode_template(data: str) -> Image:
    raw = np.frombuffer(base64.b64decode(data), np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("broken anchor template")
    return np.asarray(image, np.uint8)


class LayoutGuard:
    def __init__(self, config: GuardConfig) -> None:
        self.config = config
        self.templates = [decode_template(a.template) for a in config.anchors if a.template]
        self.rois = [a.roi for a in config.anchors if a.template]
        self.state = GuardState.OFF if not self.templates else GuardState.OK
        self._good_in_row = 0

    def score(self, rectified: Image, i: int) -> float:
        h, w = rectified.shape[:2]
        roi, template = self.rois[i], self.templates[i]
        x0, y0, x1, y1 = roi_box(roi, (w, h), self.config.search_margin)
        area = _prepare(rectified[y0:y1, x0:x1], _scale_for(roi, (w, h)))
        th, tw = template.shape
        if area.shape[0] < th or area.shape[1] < tw:
            area = cv2.copyMakeBorder(
                area,
                0,
                max(0, th - area.shape[0]),
                0,
                max(0, tw - area.shape[1]),
                cv2.BORDER_REPLICATE,
            )
        result = cv2.matchTemplate(area, template, cv2.TM_CCOEFF_NORMED)
        best = float(result.max())
        return best if np.isfinite(best) else 0.0

    def check(self, rectified: Image) -> GuardResult:
        if not self.templates:
            self.state = GuardState.OFF
            return GuardResult(self.state)
        scores = [self.score(rectified, i) for i in range(len(self.templates))]
        if min(scores) >= self.config.threshold:
            self._good_in_row += 1
            if self.state is not GuardState.OK:
                done = self._good_in_row >= self.config.recover_frames
                self.state = GuardState.OK if done else GuardState.RECOVERING
        else:
            self._good_in_row = 0
            self.state = GuardState.LOST
        return GuardResult(self.state, [round(s, 3) for s in scores])


# --- automatic anchor suggestions ---------------------------------------------------------

HISTORY_WIDTH = 320  # frames kept for suggestions are shrunk to this width


def history_frame(rectified: Image) -> Image:
    """A small max-channel gray copy of a rectified frame for anchor suggestions."""
    h, w = rectified.shape[:2]
    size = (HISTORY_WIDTH, max(8, round(h * HISTORY_WIDTH / w)))
    return gray_max(np.asarray(cv2.resize(rectified, size, interpolation=cv2.INTER_AREA), np.uint8))


def _overlap(a: Roi, b: Roi) -> bool:
    return not (a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y)


def _trim_off_fields(x0: float, y0: float, x1: float, y1: float, fields: list[Roi]) -> Roi | None:
    """Cut a box off the fields it touches above or below (captions sit right next to values);
    None if that leaves less than 70 % of its height, or it overlaps a field sideways."""
    height = y1 - y0
    for f in fields:
        if x1 <= f.x or f.x + f.w <= x0 or y1 <= f.y or f.y + f.h <= y0:
            continue
        if f.y >= (y0 + y1) / 2:  # the field is below the caption
            y1 = min(y1, f.y)
        elif f.y + f.h <= (y0 + y1) / 2:  # above
            y0 = max(y0, f.y + f.h)
        else:
            return None
    if y1 - y0 < 0.7 * height:
        return None
    return Roi(x=x0, y=y0, w=x1 - x0, h=y1 - y0)


def suggest_anchors(frames: list[Image], fields: list[Roi], count: int = 3) -> list[Roi]:
    """Places on the board that don't change over the frames and have clear structure
    (captions, logos), away from the fields: candidates for layout-guard anchors.

    frames: recent history_frame() images (a few seconds; one frame works, less reliably).
    Returns up to `count` ROIs (relative), best first, spread over the board."""
    if not frames:
        return []
    stack = np.stack([f.astype(np.float32) for f in frames])
    # Robust to a goal animation or a person covering part of the window: a pixel is static
    # when it matches its median in most frames (brightness may breathe a little).
    mean = np.median(stack, axis=0)
    h, w = mean.shape
    if len(frames) > 1:
        close = np.abs(stack - mean) <= np.maximum(8.0, 0.15 * mean)
        static = close.mean(axis=0) >= 0.6
    else:
        static = np.ones((h, w), bool)
    gx = cv2.Sobel(mean, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(mean, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.blur(np.sqrt(gx * gx + gy * gy), (3, 3))
    textured = grad > max(20.0, float(np.percentile(grad, 80)))

    free = np.ones((h, w), bool)  # not a field (with room around it)
    for r in fields:
        m = 0.05 * r.h  # captions often sit right next to the values
        x0, y0 = int((r.x - m) * w), int((r.y - m) * h)
        x1, y1 = int((r.x + r.w + m) * w) + 1, int((r.y + r.h + m) * h) + 1
        free[max(0, y0) : y1, max(0, x0) : x1] = False

    cand = (static & textured & free).astype(np.uint8)
    # merge the letters of a word into one blob
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, w // 40), max(3, h // 40)))
    blobs = cv2.dilate(cand, kernel)
    n, labels = cv2.connectedComponents(blobs, connectivity=8)
    boxes: list[tuple[float, Roi]] = []
    for i in range(1, n):
        ys, xs = np.nonzero((labels == i) & (cand > 0))  # the letters, not the merged blob
        if xs.size == 0:
            continue
        x, y = int(xs.min()), int(ys.min())
        bw, bh = int(xs.max()) - x + 1, int(ys.max()) - y + 1
        if bw < w * 0.05 or bh < h * 0.03 or bw * bh < w * h * 0.002:
            continue
        if bw > w * 0.6 or bh > h * 0.5:
            continue  # too big to be a caption: probably part of the picture
        score = float((grad * (labels == i) * cand).sum())
        pad = 0.15 * bh  # a little room around the caption
        x0, y0 = max(0.0, x - pad) / w, max(0.0, y - pad) / h
        x1, y1 = min(float(w), x + bw + pad) / w, min(float(h), y + bh + pad) / h
        roi = _trim_off_fields(x0, y0, x1, y1, fields)
        if roi is not None:
            boxes.append((score, roi))
    boxes.sort(key=lambda b: -b[0])

    chosen: list[Roi] = []
    while boxes and len(chosen) < count:

        def value(item: tuple[float, Roi]) -> float:
            score, r = item
            if not chosen:
                return score
            cx, cy = r.x + r.w / 2, r.y + r.h / 2
            d = min(abs(cx - (c.x + c.w / 2)) + abs(cy - (c.y + c.h / 2)) for c in chosen)
            return score * (0.3 + d)  # prefer anchors spread over the board

        best = max(boxes, key=value)
        boxes.remove(best)
        if not any(_overlap(best[1], c) for c in chosen):
            chosen.append(best[1])
    return chosen
