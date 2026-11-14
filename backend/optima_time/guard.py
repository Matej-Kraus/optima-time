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
    gray = gray_max(image)
    h, w = gray.shape[:2]
    size = (max(4, round(w * scale)), max(4, round(h * scale)))
    small = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
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
