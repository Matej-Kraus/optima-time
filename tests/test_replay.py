from optima_time.fields.models import ClockField, NumberField, PeriodField, Roi
from tools.replay.__main__ import clock_seconds, suspicious

ROI = Roi(x=0, y=0, w=0.5, h=0.5)
CLOCK = ClockField(id="Time", roi=ROI)
TENTHS = ClockField(id="Time", roi=ROI, tenths=True)
SCORE = NumberField(id="scoreh", roi=ROI)
PERIOD = PeriodField(id="period", roi=ROI)


def test_clock_seconds() -> None:
    assert clock_seconds("12:02") == 722
    assert clock_seconds("0:42.5") == 42.5
    assert clock_seconds("") is None
    assert clock_seconds("1x:00") is None


def test_normal_clock_steps_are_fine() -> None:
    assert suspicious(CLOCK, "12:01", "12:02") is None  # counting up
    assert suspicious(CLOCK, "1:58", "1:57") is None  # penalty counting down
    assert suspicious(CLOCK, "", "2:00") is None  # penalty appears
    assert suspicious(CLOCK, "0:01", "") is None
    assert suspicious(CLOCK, "20:00", "00:00") is None  # reset for the next period
    assert suspicious(TENTHS, "0:42.5", "0:42.4") is None


def test_impossible_steps_are_flagged() -> None:
    assert suspicious(CLOCK, "12:01", "12:07") == "step +6 s"
    assert suspicious(CLOCK, "12:01", "11:01") == "step -60 s"
    assert suspicious(SCORE, "2", "1") == "score down 2->1"
    assert suspicious(SCORE, "1", "3") == "score jump 1->3"
    assert suspicious(SCORE, "1", "2") is None
    assert suspicious(PERIOD, "1", "2") is None
    assert suspicious(PERIOD, "2", "1") == "period 2->1"
