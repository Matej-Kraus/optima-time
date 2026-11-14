from optima_time.fields.models import BlankPolicy, ClockField, NumberField, Roi
from optima_time.pipeline import ReadStatus
from tools.eval.metrics import Observation, TruthTrack, evaluate_field

ROI = Roi(x=0, y=0, w=1, h=1)
SCORE = NumberField(id="scoreh", roi=ROI)
FPS = 10.0


def obs(frame: int, value: int | None, status: ReadStatus = ReadStatus.VALID) -> Observation:
    if value is None and status is ReadStatus.VALID:
        status = ReadStatus.BLANK
    return Observation(frame, status, str(value) if value is not None else "", 0.9, value)


def track(*points: tuple[int, str, bool]) -> TruthTrack:
    t = TruthTrack()
    for frame, value, visible in points:
        t.frames.append(frame)
        t.values.append(value)
        t.visible.append(visible)
    return t


def test_perfect_reading() -> None:
    truth = track((0, "1", True), (5, "2", True))
    m = evaluate_field(SCORE, truth, [obs(i, 1 if i < 5 else 2) for i in range(10)], FPS)
    s = m.summary()
    assert s["crop_accuracy_%"] == 100.0
    assert (s["changes"], s["captured_%"], s["delay_ms_median"]) == (1, 100.0, 0.0)
    assert s["wrong_published"] == 0


def test_late_change_counts_delay_not_error() -> None:
    truth = track((0, "1", True), (5, "2", True))
    readings = [obs(i, 1 if i < 7 else 2) for i in range(10)]  # 2 frames late
    s = evaluate_field(SCORE, truth, readings, FPS).summary()
    assert s["captured_%"] == 100.0 and s["delay_ms_median"] == 200.0
    assert s["wrong_published"] == 0
    assert s["wrong_value"] == 2  # but the crops in frames 5 and 6 were misread


def test_wrong_value_is_published_once_per_episode() -> None:
    truth = track((0, "1", True))
    readings = [obs(0, 1), obs(1, 7), obs(2, 7), obs(3, 1), obs(4, 8), obs(5, 1)]
    s = evaluate_field(SCORE, truth, readings, FPS).summary()
    assert s["wrong_published"] == 2
    assert s["wrong_published_frames"] == 3


def test_hidden_field_should_hold_last_visible_value() -> None:
    # goal animation from frame 3: the board shows something else; holding "1" is right
    truth = track((0, "1", True), (3, "1", False), (6, "1", True))
    readings = [obs(0, 1), obs(1, 1), obs(2, 1), obs(3, 8), obs(4, None), obs(5, None), obs(6, 1)]
    s = evaluate_field(SCORE, truth, readings, FPS).summary()
    assert s["wrong_published"] == 1  # the 8 read during the animation
    assert s["lit_crops"] == 4  # hidden frames don't count for crop accuracy


def test_unlit_field_read_as_value() -> None:
    pen = ClockField(id="penaltyh1", roi=ROI, blank=BlankPolicy.CLEAR, blank_delay_ms=200)
    truth = track((0, "", True))
    readings = [
        Observation(0, ReadStatus.BLANK, "", 0.0, None),
        Observation(1, ReadStatus.VALID, "0:00", 0.6, (0, False)),
        Observation(2, ReadStatus.BLANK, "", 0.0, None),
    ]
    s = evaluate_field(pen, truth, readings, FPS).summary()
    assert s["unlit_read_as_value"] == 1
    assert s["wrong_published"] == 1


def test_clear_policy_publishes_blank_after_delay() -> None:
    pen = ClockField(id="penaltyh1", roi=ROI, blank=BlankPolicy.CLEAR, blank_delay_ms=200)
    truth = track((0, "0:02", True), (3, "", True))
    readings = [
        Observation(0, ReadStatus.VALID, "0:02", 0.9, (20, False)),
        Observation(1, ReadStatus.VALID, "0:02", 0.9, (20, False)),
        Observation(2, ReadStatus.VALID, "0:02", 0.9, (20, False)),
    ] + [Observation(i, ReadStatus.BLANK, "", 0.0, None) for i in range(3, 8)]
    s = evaluate_field(pen, truth, readings, FPS).summary()
    assert s["captured_%"] == 100.0
    assert s["delay_ms_median"] == 100.0  # cleared on the 2nd blank frame (200 ms at 10 fps)
    assert s["wrong_published"] == 0


def test_reading_the_real_value_behind_an_occlusion_is_not_wrong() -> None:
    truth = track((0, "1", True), (3, "1", False), (4, "2", False), (6, "2", True))
    readings = [obs(0, 1), obs(1, 1), obs(2, 1), obs(3, 1), obs(4, 2), obs(5, 2), obs(6, 2)]
    assert evaluate_field(SCORE, truth, readings, FPS).summary()["wrong_published"] == 0
