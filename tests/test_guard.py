import cv2
import numpy as np
import pytest

from optima_time.config.models import AnchorConfig, GuardConfig
from optima_time.fields.models import Roi
from optima_time.guard import GuardState, LayoutGuard, capture_template

ANCHOR = Roi(x=0.3, y=0.4, w=0.4, h=0.15)


def board(brightness: float = 1.0, shift: int = 0) -> np.ndarray:
    img = np.zeros((300, 600, 3), np.uint8)
    cv2.putText(
        img, "PERIODA", (190 + shift, 155), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (230, 230, 230), 3
    )
    return np.clip(img.astype(np.float32) * brightness, 0, 255).astype(np.uint8)


def animation(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.zeros((300, 600, 3), np.uint8)
    for _ in range(8):
        x, y = rng.integers(0, 560), rng.integers(0, 260)
        cv2.rectangle(
            img, (int(x), int(y)), (int(x) + 80, int(y) + 50), rng.integers(0, 255, 3).tolist(), -1
        )
    cv2.putText(img, "GOL!", (200, 200), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 8)
    return img


def guard(**kw) -> LayoutGuard:
    template = capture_template(board(), ANCHOR)
    return LayoutGuard(GuardConfig(anchors=[AnchorConfig(roi=ANCHOR, template=template)], **kw))


def test_no_anchors_means_off_and_ok() -> None:
    g = LayoutGuard(GuardConfig())
    r = g.check(board())
    assert r.state is GuardState.OFF and r.ok


def test_layout_matches_despite_exposure_and_small_shift() -> None:
    g = guard()
    for b, s in [(1.0, 0), (0.6, 0), (1.4, 0), (1.0, 6), (0.7, -5)]:
        r = g.check(board(b, s))
        assert r.ok, (b, s, r.scores)
        assert r.scores[0] > 0.8


def test_foreign_content_is_detected_and_recovery_needs_n_frames() -> None:
    g = guard(recover_frames=5)
    assert g.check(board()).ok
    for seed in range(20):
        r = g.check(animation(seed))
        assert not r.ok and r.state is GuardState.LOST, r.scores
    states = [g.check(board()).state for _ in range(6)]
    assert states[:4] == [GuardState.RECOVERING] * 4
    assert states[4] is GuardState.OK


def test_dark_board_is_lost() -> None:
    g = guard()
    assert not g.check(np.zeros((300, 600, 3), np.uint8)).ok


def test_flat_anchor_is_refused() -> None:
    with pytest.raises(ValueError):
        capture_template(np.zeros((300, 600, 3), np.uint8), ANCHOR)


def test_resolution_change_keeps_working() -> None:
    g = guard()
    big = cv2.resize(board(), (1200, 600))
    assert g.check(np.asarray(big, np.uint8)).ok
