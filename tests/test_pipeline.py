"""Pipeline tests with a fake recognizer (no model needed): gates, status and format handling."""

import cv2
import numpy as np

from optima_time.config.models import DetectionConfig, Profile
from optima_time.fields.formats import ClockStyle
from optima_time.fields.models import ClockField, NumberField, Roi
from optima_time.pipeline import Pipeline, ReadStatus
from optima_time.recognizers.base import Crop, Reading
from optima_time.sources.base import Frame

LEFT = Roi(x=0.0, y=0.0, w=0.5, h=1.0)
RIGHT = Roi(x=0.5, y=0.0, w=0.5, h=1.0)


class FakeRecognizer:
    """Returns scripted texts in call order."""

    name = "fake"

    def __init__(self, script: list[list[tuple[str, float]]]):
        self.script = script
        self.calls: list[list[Crop]] = []

    def read(self, crops: list[Crop]) -> list[Reading]:
        self.calls.append(crops)
        out = self.script.pop(0)
        return [Reading(t, c, engine=self.name) for t, c in out]


def frame(seq: int = 1, lit: tuple[bool, bool] = (True, True)) -> Frame:
    img = np.zeros((100, 200, 3), np.uint8)
    for i, on in enumerate(lit):
        if on:
            img[30:70, i * 100 + 20 : i * 100 + 80] = 255  # something bright in each half
    return Frame(img, seq, 0, seq / 25)


def pipeline(rec: FakeRecognizer, detection: bool = False) -> Pipeline:
    profile = Profile(
        fields=[
            ClockField(id="Time", roi=LEFT, tenths=True, style=ClockStyle.NO_LEADING_ZERO),
            NumberField(id="scoreh", roi=RIGHT),
        ],
        detection=DetectionConfig(enabled=detection),
    )
    return Pipeline(profile, recognizer_factory=lambda _model: rec)


def test_valid_reads_are_rendered() -> None:
    rec = FakeRecognizer([[("05:13", 0.99), ("03", 0.97)]])
    result = pipeline(rec).process(frame())
    t, s = result.fields["Time"], result.fields["scoreh"]
    assert (t.status, t.text) == (ReadStatus.VALID, "5:13")
    assert (s.status, s.text) == (ReadStatus.VALID, "3")
    assert len(rec.calls) == 1 and len(rec.calls[0]) == 2  # one batch per model
    assert rec.calls[0][0].allowed == "0123456789:."


def test_contrast_gate_skips_ocr() -> None:
    rec = FakeRecognizer([[("05:13", 0.99)]])
    result = pipeline(rec).process(frame(lit=(True, False)))
    assert result.fields["scoreh"].status is ReadStatus.BLANK
    assert result.fields["scoreh"].reading is None
    assert len(rec.calls[0]) == 1


def test_low_confidence_invalid_and_empty() -> None:
    rec = FakeRecognizer([[("05:13", 0.3), ("123", 0.99)], [("", 0.0), ("4", 0.99)]])
    p = pipeline(rec)
    r1 = p.process(frame(1))
    assert r1.fields["Time"].status is ReadStatus.LOW_CONFIDENCE
    assert r1.fields["scoreh"].status is ReadStatus.INVALID  # 3 digits > max_digits
    r2 = p.process(frame(2))
    assert r2.fields["Time"].status is ReadStatus.BLANK
    assert r2.fields["scoreh"].text == "4"


def test_last_valid_value_resolves_missing_separator() -> None:
    rec = FakeRecognizer([[("54.8", 0.99), ("1", 0.99)], [("547", 0.99), ("1", 0.99)]])
    p = pipeline(rec)
    p.process(frame(1))
    assert p.process(frame(2)).fields["Time"].text == "54.7"


def test_disabled_field_is_not_read() -> None:
    rec = FakeRecognizer([[("05:13", 0.99)]])
    p = pipeline(rec)
    profile = p.profile.model_copy(deep=True)
    profile.fields[1].enabled = False
    p.update_profile(profile)
    assert set(p.process(frame()).fields) == {"Time"}


def test_rectifier_follows_frame_size() -> None:
    rec = FakeRecognizer([[("05:13", 0.99), ("1", 0.99)], [("05:12", 0.99), ("1", 0.99)]])
    p = pipeline(rec)
    p.process(frame())
    big = Frame(np.zeros((200, 400, 3), np.uint8), 2, 0)
    big.image[60:140, 40:160] = 255
    big.image[60:140, 240:360] = 255
    assert p.process(big).fields["Time"].text == "5:12"


# --- change detection (SPEC 10.5)


def digit_frame(seq: int, text: str, gain: float = 1.0) -> Frame:
    img = np.zeros((100, 200, 3), np.uint8)
    cv2.putText(img, text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (40, 255, 40), 5)
    cv2.putText(img, "3", (130, 70), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 230, 20), 5)
    img = np.clip(img.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    return Frame(img, seq, 0, seq / 25)


def test_unchanged_crops_are_not_read_again() -> None:
    rec = FakeRecognizer([[("12", 0.99), ("3", 0.99)]] * 10)
    p = pipeline(rec, detection=True)
    p.process(digit_frame(1, "12"))
    for i in range(2, 6):  # same picture, slightly flickering
        r = p.process(digit_frame(i, "12", gain=1.0 + 0.04 * (-1) ** i))
        assert r.fields["Time"].cached and r.fields["Time"].text == "1.2"
    assert len(rec.calls) == 1


def test_changed_digit_is_read() -> None:
    rec = FakeRecognizer([[("12", 0.99), ("3", 0.99)], [("13", 0.99)]])
    p = pipeline(rec, detection=True)
    p.process(digit_frame(1, "12"))
    r = p.process(digit_frame(2, "13"))
    assert not r.fields["Time"].cached and r.fields["scoreh"].cached
    assert len(rec.calls) == 2 and len(rec.calls[1]) == 1


def test_must_read_and_max_age_force_a_read() -> None:
    rec = FakeRecognizer([[("12", 0.99), ("3", 0.99)], [("3", 0.99)], [("12", 0.99), ("3", 0.99)]])
    p = pipeline(rec, detection=True)
    p.process(digit_frame(1, "12"))
    r = p.process(digit_frame(2, "12"), must_read={"scoreh"})
    assert r.fields["Time"].cached and not r.fields["scoreh"].cached
    r = p.process(digit_frame(40, "12"))  # 1.56 s later: older than max_age
    assert not r.fields["Time"].cached and not r.fields["scoreh"].cached
