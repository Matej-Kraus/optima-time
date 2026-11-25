"""Confirmation, plausibility, blank policy and manual hold (SPEC 11.4-11.6)."""

from optima_time.fields.confirm import FieldLogic, FieldStatus
from optima_time.fields.formats import ClockStyle
from optima_time.fields.models import (
    BlankPolicy,
    ClockField,
    Direction,
    NumberField,
    PeriodField,
    Roi,
)
from optima_time.pipeline import FieldRead, ReadStatus
from optima_time.recognizers.base import Reading

ROI = Roi(x=0, y=0, w=1, h=1)
MS = 1_000_000
FRAME = 40 * MS  # 25 fps


class Feeder:
    """Feeds readings one frame (40 ms) apart and records the published text."""

    def __init__(self, field) -> None:
        self.logic = FieldLogic(field)
        self.field = field
        self.t = 0
        self.events: list = []

    def read(self, text: str | None, conf: float = 0.99) -> str:
        """text None = blank (contrast gate); returns the published text after this frame."""
        if text is None:
            r = FieldRead(self.field.id, ReadStatus.BLANK, 0.0)
        else:
            value = self.field.parse(text, self.logic.published)
            status = ReadStatus.VALID if value is not None else ReadStatus.INVALID
            if conf < self.field.min_confidence:
                status, value = ReadStatus.LOW_CONFIDENCE, None
            r = FieldRead(self.field.id, status, 100.0, Reading(text, conf), value)
        self.events += self.logic.update(r, self.t)
        self.t += FRAME
        return self.logic.text

    def reads(self, text: str | None, n: int, conf: float = 0.99) -> str:
        for _ in range(n):
            self.read(text, conf)
        return self.logic.text


def clock(**kw) -> Feeder:
    return Feeder(ClockField(id="Time", roi=ROI, tenths=True, style=ClockStyle.AS_IS, **kw))


def started_clock(value: str = "05:00", **kw) -> Feeder:
    f = clock(**kw)
    f.reads(value, 11)  # initial: 3 reads over 400 ms
    assert f.logic.text == value
    return f


# --- clock ---


def test_clock_initial_value_needs_time() -> None:
    f = clock()
    assert f.reads("05:00", 3) == ""  # 3 reads but only 80 ms
    assert f.reads("05:00", 8) == "05:00"  # >= 400 ms


def test_clock_tick_is_accepted_at_once() -> None:
    f = started_clock("05:00")
    assert f.read("04:59") == "04:59"
    assert f.logic.status is FieldStatus.NEW


def test_clock_tick_with_low_confidence_needs_two_reads() -> None:
    f = started_clock("05:00")
    assert f.read("04:59", conf=0.6) == "05:00"
    assert f.read("04:59", conf=0.6) == "04:59"


def test_clock_misread_jump_is_never_published() -> None:
    # spike/eval case: a half-covered 0 read as 3 for three frames
    f = started_clock("01:42")
    f.read("01:41")
    for text in ["31:41", "31:41", "31:41", "01:41", "01:40"]:
        assert f.read(text) in {"01:41", "01:40"}
    assert any(e.kind == "rejected" for e in f.events)


def test_clock_real_jump_is_accepted_after_holding() -> None:
    f = started_clock("0.0")  # period over
    out = [f.read("20:00") for _ in range(12)]  # new period, clock stopped at 20:00
    assert out[0] == "0.0" and out[-1] == "20:00"
    assert out.index("20:00") >= 10  # >= 400 ms


def test_clock_jump_that_keeps_running_is_confirmed() -> None:
    # a corrected clock that keeps ticking while it is being confirmed
    f = started_clock("10:00")
    seq = ["12:30"] * 5 + ["12:29"] * 5 + ["12:28"] * 2
    out = [f.read(t) for t in seq]
    assert out[-1] == "12:28"
    assert "12:30" not in out[:9]


def test_last_minute_transition_to_tenths() -> None:
    f = started_clock("01:00")
    assert f.read("59.9") == "59.9"
    assert f.read("59.8") == "59.8"


def test_direction_is_learned_and_enforced() -> None:
    f = started_clock("05:00")
    f.read("04:59")
    f.read("04:58")
    assert f.logic.direction is Direction.DOWN
    assert f.read("04:59") == "04:58"  # going up is now unexpected


def test_fixed_direction_from_profile() -> None:
    f = started_clock("05:00", direction=Direction.UP)
    assert f.read("04:59") == "05:00"
    assert f.read("05:01") == "05:01"


# --- penalties: blank policy ---


def penalty() -> Feeder:
    return Feeder(ClockField(id="penaltyh1", roi=ROI, blank=BlankPolicy.CLEAR, blank_delay_ms=400))


def test_penalty_appears_after_two_reads_and_clears_after_delay() -> None:
    f = penalty()
    f.reads(None, 12)
    f.reads("1:00", 11)  # initial value
    assert f.logic.text == "1:00"
    assert f.reads(None, 5) == "1:00"  # 160 ms blank: still there
    assert f.reads(None, 7) == ""  # >= 400 ms: cleared
    assert f.read("2:00") == ""  # appear: 1st read
    assert f.read("2:00") == "2:00"  # 2nd read
    assert f.read("1:59") == "1:59"  # tick


def test_penalty_zero_can_clear_immediately_without_changing_old_profiles() -> None:
    old = penalty()
    old.reads("0:01", 11)
    assert old.read("0:00") == "0:00"

    f = Feeder(
        ClockField(
            id="penaltyh1",
            roi=ROI,
            blank=BlankPolicy.CLEAR,
            blank_delay_ms=2000,
            zero_is_blank=True,
        )
    )
    f.reads("0:01", 11)
    assert f.read("0:00") == ""


def test_new_penalty_template_delay_keeps_short_blank() -> None:
    f = Feeder(
        ClockField(
            id="penaltyh1",
            roi=ROI,
            blank=BlankPolicy.CLEAR,
            blank_delay_ms=2000,
            zero_is_blank=True,
        )
    )
    f.reads("1:00", 11)
    assert f.reads(None, 45) == "1:00"  # 1.76 s since the first blank
    assert f.reads(None, 7) == ""  # at least 2 s


def test_hold_policy_keeps_value_when_blank() -> None:
    f = started_clock("05:00")
    assert f.reads(None, 50) == "05:00"


def test_value_policy_writes_given_text() -> None:
    f = Feeder(NumberField(id="s", roi=ROI, blank=BlankPolicy.VALUE, blank_value="0"))
    f.reads("3", 3)
    assert f.reads(None, 12) == "0"


def test_short_blank_flicker_does_not_clear() -> None:
    f = penalty()
    f.reads("1:00", 11)
    for _ in range(10):
        f.reads(None, 3)  # 120 ms blank
        f.read("1:00")
    assert f.logic.text == "1:00"


# --- score ---


def score() -> Feeder:
    return Feeder(NumberField(id="scoreh", roi=ROI))


def test_score_plus_one_after_two_reads() -> None:
    f = score()
    assert f.reads("9", 3) == "9"
    assert f.read("10") == "9"
    assert f.read("10") == "10"


def test_score_decrease_or_jump_must_hold_two_seconds() -> None:
    f = score()
    f.reads("3", 3)
    assert f.reads("5", 49) == "3"  # 1.92 s
    assert f.reads("5", 3) == "5"
    f2 = score()
    f2.reads("3", 3)
    assert f2.reads("2", 40) == "3"
    assert f2.reads("2", 12) == "2"  # a referee's correction gets through


def test_score_noise_never_published() -> None:
    f = score()
    f.reads("3", 3)
    for text in ["8", "3", "5", "3", "6", "6", "3"] * 20:
        assert f.read(text) == "3"


def test_low_confidence_and_invalid_are_rejected() -> None:
    f = score()
    f.reads("3", 3)
    assert f.read("4", conf=0.2) == "3"
    assert f.logic.status is FieldStatus.REJECTED
    assert f.read("123") == "3"


# --- period ---


def test_period_needs_three_reads_for_plus_one() -> None:
    f = Feeder(PeriodField(id="period", roi=ROI))
    f.reads("1", 3)
    assert f.reads("2", 2) == "1"
    assert f.read("2") == "2"


# --- manual hold and stale ---


def test_manual_hold_overrides_ocr_until_released() -> None:
    f = score()
    f.reads("3", 3)
    f.events += f.logic.hold("4")
    assert f.logic.text == "4"
    assert f.reads("3", 100) == "4"
    assert f.logic.status is FieldStatus.HELD
    f.events += f.logic.release()
    assert f.logic.text == "4"  # stays until OCR confirms
    assert f.reads("3", 3) == "3"


def test_stale_drops_candidate_and_keeps_value() -> None:
    f = score()
    f.reads("3", 3)
    f.read("4")
    f.logic.stale()
    assert f.logic.status is FieldStatus.STALE and f.logic.candidate is None
    assert f.read("4") == "3"  # starts over: needs 2 reads again
    assert f.read("4") == "4"


def test_events() -> None:
    f = score()
    f.reads("3", 3)
    f.read("7")
    f.read("3")
    kinds = [e.kind for e in f.events]
    assert kinds == ["changed", "rejected"]


def test_clock_catches_up_after_a_gap_without_reads() -> None:
    f = started_clock("01:05")
    f.read("01:04")
    f.read("01:03")  # direction learned: down
    for _ in range(45):  # 1.8 s without reads (goal animation, layout guard)
        f.logic.stale()
        f.t += FRAME
    assert f.read("01:01") == "01:03"  # moved by less than the gap: 2 reads
    assert f.read("01:01") == "01:01"


def test_gap_does_not_allow_jumps_beyond_elapsed_time_or_backwards() -> None:
    f = started_clock("01:05")
    f.read("01:04")
    f.read("01:03")
    for _ in range(25):  # 1 s gap
        f.logic.stale()
        f.t += FRAME
    assert f.reads("00:41", 2) == "01:03"  # 22 s in 1 s: no
    assert f.reads("01:09", 2) == "01:03"  # backwards: no


def test_penalty_moving_up_from_the_next_slot_is_accepted_fast() -> None:
    f = penalty()
    f.reads("0:02", 11)
    f.read("0:01")
    peer = [f.field.parse("0:21", None)]
    assert all(peer)

    def r(text: str) -> None:
        value = f.field.parse(text, None)
        read = FieldRead("penaltyh1", ReadStatus.VALID, 100.0, Reading(text, 0.99), value)
        f.logic.update(read, f.t, peer)

    r("0:21")
    f.t += FRAME
    r("0:21")
    f.t += FRAME
    assert f.logic.text == "0:21"  # 2 reads, not 400 ms


def test_jump_without_a_matching_sibling_stays_slow() -> None:
    f = penalty()
    f.reads("0:02", 11)
    f.read("0:01")
    assert f.reads("0:21", 3) == "0:01"  # 120 ms: still waiting


def test_group_of_field_ids() -> None:
    from optima_time.state import group

    assert group("penaltyh1") == group("penaltyh2") == "penaltyh"
    assert group("penaltya1") != group("penaltyh1")
    assert group("Time") == "Time"
