"""The synthetic generator's ground truth must be right, or every evaluation number is wrong."""

from tools.synth.board import BOXES, COLS, ROWS, Camera, CameraStyle, LedStyle, led_board
from tools.synth.timeline import FIELDS, clock_text, penalty_text, simulate


def test_clock_texts() -> None:
    assert clock_text(12000, True) == "20:00"
    assert clock_text(601, True) == "01:01"  # ceil to whole seconds above a minute
    assert clock_text(600, True) == "01:00"
    assert clock_text(599, True) == "59.9"
    assert clock_text(0, True) == "0.0"
    assert clock_text(599, False) == "01:00"
    assert penalty_text(1200) == "2:00"
    assert penalty_text(1191) == "2:00"


def test_default_scenario_covers_the_hard_cases() -> None:
    tl = simulate(1)
    times = {s.as_dict()["Time"] for s in tl.states}
    assert {"23:54", "01:00", "59.9", "0.0", "20:00"} <= times
    scores = [int(s.as_dict()["scoreh"]) for s in tl.states]
    assert 9 in scores and 10 in scores  # 9 -> 10
    assert any(s.as_dict()["penaltyh2"] for s in tl.states)  # two penalties at once
    assert {s.as_dict()["period"] for s in tl.states} == {"1", "2"}
    assert {iv.kind for iv in tl.intervals} == {"foreign", "occlusion"}


def test_foreign_content_hides_every_field() -> None:
    tl = simulate(1, short=True)
    foreign = next(iv for iv in tl.intervals if iv.kind == "foreign")
    assert tl.hidden(foreign.start) == set(FIELDS)
    assert tl.hidden(0) == set()


def test_occluder_covers_fields_geometrically() -> None:
    led = LedStyle()
    cam = Camera(CameraStyle(), (ROWS * led.pitch, COLS * led.pitch), seed=0)
    covered = cam.covered_boxes(0.2, BOXES, led.pitch, 0.15)
    assert "scoreh" in covered and "scorea" not in covered
    assert cam.covered_boxes(0.99, BOXES, led.pitch, 0.15) == set()  # off the board


def test_board_render_shape() -> None:
    led = LedStyle()
    img = led_board({"Time": "12:34"}, led)
    assert img.shape == (ROWS * led.pitch, COLS * led.pitch, 3)
    x, y, w, h = BOXES["Time"]
    p = led.pitch
    assert img[y * p : (y + h) * p, x * p : (x + w) * p, 1].max() > 200  # green clock lit


def test_all_board_fonts_render_every_character() -> None:
    texts = {
        "Time": "12:34",
        "period": "4",
        "scoreh": "10",
        "scorea": "98",
        "penaltyh1": "1:45",
        "penaltyh2": "0:07",
        "penaltya1": "56.9",
        "penaltya2": "",
    }
    for font in ("sans", "seg7", "dot"):
        led = LedStyle(font=font)
        img = led_board(texts, led)
        x, y, w, h = BOXES["scorea"]
        p = led.pitch
        assert img[y * p : (y + h) * p, x * p : (x + w) * p].max() > 200, font
