import pytest

from optima_time.fields.formats import (
    Align,
    ClockSpec,
    ClockStyle,
    ClockValue,
    NumberSpec,
    NumberStyle,
    PeriodSpec,
    align,
    parse_clock,
    parse_number,
    parse_period,
    render_clock,
    render_number,
    render_period,
)

GAME = ClockSpec(tenths=True)
PENALTY = ClockSpec(tenths=False)


def clock(text: str, spec: ClockSpec = GAME) -> ClockValue:
    value = parse_clock(text, spec)
    assert value is not None, text
    return value


@pytest.mark.parametrize(
    ("text", "tenths", "board", "has_tenths"),
    [
        ("12:45", 7650, "12:45", False),
        ("00:00", 0, "00:00", False),
        ("0:00", 0, "0:00", False),
        ("20:00", 12000, "20:00", False),
        ("23:54", 14340, "23:54", False),  # warm-up / intermission: no 20:00 limit
        ("120:00", 72000, "120:00", False),  # three-digit minutes
        ("54.7", 547, "54.7", True),
        ("0.0", 0, "0.0", True),
        ("5.3", 53, "5.3", True),
        ("１２：４５", 7650, "12:45", False),  # noqa: RUF001 - full-width (NFKC)
        (" 12 : 45 ", 7650, "12:45", False),
    ],
)
def test_parse_clock_valid(text: str, tenths: int, board: str, has_tenths: bool) -> None:
    value = clock(text)
    assert (value.tenths, value.board, value.has_tenths) == (tenths, board, has_tenths)


@pytest.mark.parametrize(
    "text",
    [
        "",
        ":",
        "12:60",  # seconds >= 60
        "60.0",  # ss.d with 60 s
        "12:345",
        "1:2:3",
        ":45",
        "1234567",
        "abc",
    ],
)
def test_parse_clock_invalid(text: str) -> None:
    assert parse_clock(text, GAME) is None


def test_tenths_rejected_when_board_has_none() -> None:
    assert parse_clock("54.7", PENALTY) is None
    assert parse_clock("547", PENALTY) == clock("5:47", PENALTY)


def test_max_minutes() -> None:
    assert parse_clock("25:00", ClockSpec(max_minutes=20)) is None


# --- separator repair (the most common confident OCR error in spike A) ---


def test_confused_separator() -> None:
    assert clock("02.44") == clock("02:44")  # two digits after: mm:ss
    assert clock("54:7") == clock("54.7")  # one digit after: ss.d


def test_missing_separator_unambiguous() -> None:
    assert clock("1245") == clock("12:45")
    assert clock("0128", PENALTY) == clock("01:28", PENALTY)


def test_missing_separator_ambiguous_needs_last_value() -> None:
    # "547" is 5:47 or 54.7
    assert parse_clock("547", GAME) is None
    assert parse_clock("547", GAME, last=clock("54.8")) == clock("54.7")
    assert parse_clock("547", GAME, last=clock("5:48")) == clock("5:47")


# --- rendering ---


@pytest.mark.parametrize(
    ("text", "style", "out"),
    [
        ("00:00", ClockStyle.AS_IS, "00:00"),
        ("00:00", ClockStyle.NO_LEADING_ZERO, "0:00"),  # what the reference app sends today
        ("05:13", ClockStyle.NO_LEADING_ZERO, "5:13"),
        ("5:13", ClockStyle.LEADING_ZERO, "05:13"),
        ("12:45", ClockStyle.NO_LEADING_ZERO, "12:45"),
        ("54.7", ClockStyle.NO_LEADING_ZERO, "54.7"),
        ("05.3", ClockStyle.NO_LEADING_ZERO, "5.3"),
        ("05.3", ClockStyle.AS_IS, "05.3"),
        ("02:00", ClockStyle.AS_IS, "02:00"),
    ],
)
def test_render_clock(text: str, style: ClockStyle, out: str) -> None:
    assert render_clock(clock(text), style) == out


def test_last_minute_transition_values_are_ordered() -> None:
    # 1:00 -> 59.9: one tenth apart, so plausibility can treat it as a normal step
    assert clock("1:00").tenths - clock("59.9").tenths == 1


# --- number ---


SCORE = NumberSpec(min_digits=1, max_digits=2, style=NumberStyle.STRIP_ZEROS)


@pytest.mark.parametrize(("text", "value"), [("0", 0), ("9", 9), ("10", 10), ("03", 3), ("99", 99)])
def test_parse_number(text: str, value: int) -> None:
    parsed = parse_number(text, SCORE)
    assert parsed is not None and parsed.value == value


@pytest.mark.parametrize("text", ["", "100", "a"])
def test_parse_number_invalid(text: str) -> None:
    assert parse_number(text, SCORE) is None


def test_render_number_styles() -> None:
    value = parse_number("03", SCORE)
    assert value is not None
    assert render_number(value, SCORE) == "3"
    assert render_number(value, NumberSpec(style=NumberStyle.AS_IS)) == "03"
    nine = parse_number("9", SCORE)
    assert nine is not None
    assert render_number(nine, NumberSpec(max_digits=2, style=NumberStyle.PAD_ZEROS)) == "09"


# --- period ---


def test_period() -> None:
    spec = PeriodSpec(min_value=1, max_value=4)
    for text in ("1", "2", "3", "4"):
        value = parse_period(text, spec)
        assert value is not None and render_period(value, spec) == text
    for text in ("0", "5", "12", ""):
        assert parse_period(text, spec) is None


def test_period_names() -> None:
    spec = PeriodSpec(names=((1, "1. tretina"), (4, "predĺženie")))
    one, two, four = (parse_period(t, spec) for t in "124")
    assert one and two and four
    assert render_period(one, spec) == "1. tretina"
    assert render_period(two, spec) == "2"
    assert render_period(four, spec) == "predĺženie"


def test_align() -> None:
    assert align("5:13", Align.RIGHT, 5) == " 5:13"
    assert align("5:13", Align.LEFT, 5) == "5:13 "
    assert align("5:13", Align.NONE, 5) == "5:13"
