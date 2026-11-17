import cv2
import numpy as np
import pytest

from optima_time.fields.models import Roi
from optima_time.geometry import Rectifier, crop, roi_box


def board_pattern(w: int = 400, h: int = 200) -> np.ndarray:
    """A board-like test image: distinct marks in each corner and a bar in the middle."""
    img = np.zeros((h, w, 3), np.uint8)
    cv2.rectangle(img, (10, 10), (60, 50), (0, 0, 255), -1)  # red, top-left
    cv2.rectangle(img, (w - 60, 10), (w - 10, 50), (0, 255, 0), -1)  # green, top-right
    cv2.rectangle(img, (w - 60, h - 50), (w - 10, h - 10), (255, 0, 0), -1)  # blue, bottom-right
    cv2.rectangle(img, (150, 80), (250, 120), (255, 255, 255), -1)
    return img


CORNERS_PX = np.array([[300, 150], [1500, 220], [1450, 800], [350, 760]], dtype=np.float32)
FRAME = (1920, 1080)


def camera_frame(pattern: np.ndarray) -> np.ndarray:
    h, w = pattern.shape[:2]
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(src, CORNERS_PX)
    return cv2.warpPerspective(pattern, m, FRAME)


def corners_rel() -> list[tuple[float, float]]:
    return [(float(x) / FRAME[0], float(y) / FRAME[1]) for x, y in CORNERS_PX]


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(
        cv2.matchTemplate(a.astype(np.float32), b.astype(np.float32), cv2.TM_CCOEFF_NORMED)[0, 0]
    )


def test_rectify_recovers_board() -> None:
    pattern = board_pattern()
    rect = Rectifier.create(corners_rel(), FRAME, max_width=1280)
    out = rect.warp(camera_frame(pattern))
    assert out.shape[1] == rect.size[0] and out.shape[0] == rect.size[1]
    assert similarity(pattern, out) > 0.9


def test_size_limited_by_max_width_and_keeps_aspect() -> None:
    rect = Rectifier.create(corners_rel(), FRAME, max_width=600)
    w, h = rect.size
    assert w == 600
    assert 1.6 < w / h < 2.2  # board in this frame is ~1175 x 595 px


def test_rectify_never_upscales() -> None:
    rect = Rectifier.create(corners_rel(), FRAME, max_width=4000)
    assert rect.size[0] < 1300


@pytest.mark.parametrize("rotate", [90, 180, 270])
def test_rotation(rotate: int) -> None:
    pattern = board_pattern()
    base = Rectifier.create(corners_rel(), FRAME)
    rect = Rectifier.create(corners_rel(), FRAME, rotate=rotate)
    out = rect.warp(camera_frame(pattern))
    code = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    expected = cv2.rotate(base.warp(camera_frame(pattern)), code[rotate])
    assert rect.size == (expected.shape[1], expected.shape[0])
    assert similarity(expected, out) > 0.95


def test_point_roundtrip() -> None:
    rect = Rectifier.create(corners_rel(), FRAME, rotate=90)
    pts = [(0.1, 0.2), (0.5, 0.5), (0.9, 0.7)]
    back = rect.to_source(rect.to_rectified(pts))
    assert np.allclose(pts, back, atol=1e-6)


def test_corners_map_to_rectified_corners() -> None:
    rect = Rectifier.create(corners_rel(), FRAME)
    out = rect.to_rectified(corners_rel())
    assert np.allclose(out, [(0, 0), (1, 0), (1, 1), (0, 1)], atol=1e-6)


def test_wrong_frame_size_rejected() -> None:
    rect = Rectifier.create(corners_rel(), FRAME)
    with pytest.raises(ValueError):
        rect.warp(np.zeros((720, 1280, 3), np.uint8))


def test_roi_box_margin_and_clamp() -> None:
    roi = Roi(x=0.0, y=0.5, w=0.5, h=0.2)
    assert roi_box(roi, (1000, 500), 0.0) == (0, 250, 500, 350)
    # margin 0.5 x ROI height (100 px) = 50 px, clamped at the left edge
    assert roi_box(roi, (1000, 500), 0.5) == (0, 200, 550, 400)


def test_crop_is_a_copy() -> None:
    img = np.zeros((100, 100, 3), np.uint8)
    c = crop(img, Roi(x=0.1, y=0.1, w=0.2, h=0.2))
    c[:] = 255
    assert img.max() == 0


def test_aspect_corrects_a_board_seen_from_the_side() -> None:
    import numpy as np

    from optima_time.geometry import rectified_size

    # a 16:10 board seen from the left: the far (right) edge is shorter, the width shrinks
    side = np.array([(170, 50), (820, 200), (820, 545), (170, 690)], dtype=np.float64)
    w, h = rectified_size(side, 4096)
    assert w / h < 1.45  # squeezed when left automatic (the real board is 1.6)
    w, h = rectified_size(side, 4096, aspect=1.6)
    assert abs(w / h - 1.6) < 0.01 and h >= 490  # the longer side keeps its resolution
    w, h = rectified_size(side, 640, aspect=1.6)
    assert w == 640
