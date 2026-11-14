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


def test_suggested_anchors_are_the_static_captions() -> None:
    from optima_time.geometry import Rectifier
    from optima_time.guard import history_frame, suggest_anchors
    from tools.synth.board import (
        BOXES,
        COLS,
        LABELS,
        ROWS,
        Camera,
        CameraStyle,
        LedStyle,
        led_board,
    )

    style, led = CameraStyle(), LedStyle()
    rect = Rectifier.create(list(style.corners), (1920, 1080))
    frames = []
    for i, t in enumerate(["12:34", "12:33", "12:32", "12:31"]):
        board = led_board({"Time": t, "scoreh": "3", "scorea": "1", "period": "2"}, led)
        frames.append(
            history_frame(rect.warp(Camera(style, board.shape[:2], seed=i).shoot(board, i)))
        )
    fields = [Roi(x=x / COLS, y=y / ROWS, w=w / COLS, h=h / ROWS) for x, y, w, h in BOXES.values()]
    found = suggest_anchors(frames, fields)
    names = set()
    for s in found:
        for name, (x, y, w, h) in LABELS.items():
            label = Roi(x=x / COLS, y=y / ROWS, w=w / COLS, h=h / ROWS)
            if not (
                s.x + s.w <= label.x
                or label.x + label.w <= s.x
                or s.y + s.h <= label.y
                or label.y + label.h <= s.y
            ):
                names.add(name)
        assert not any(  # never on a field
            not (s.x + s.w <= f.x or f.x + f.w <= s.x or s.y + s.h <= f.y or f.y + f.h <= s.y)
            for f in fields
        )
    assert names == {"PERIÓDA", "DOMÁCI", "HOSTIA"}


def test_no_suggestions_without_frames() -> None:
    from optima_time.guard import suggest_anchors

    assert suggest_anchors([], []) == []
