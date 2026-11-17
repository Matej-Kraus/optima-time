import numpy as np

from optima_time.config.models import Profile
from optima_time.fields.confirm import FieldLogic, FieldStatus
from optima_time.fields.models import IndicatorField, Roi
from optima_time.pipeline import Pipeline, ReadStatus
from optima_time.sources.base import Frame

LAMP = IndicatorField(
    id="timeout_h", roi=Roi(x=0.4, y=0.4, w=0.2, h=0.2), on_text="TO", off_text=""
)


def frame(lit: bool, seq: int) -> Frame:
    image = np.full((100, 200, 3), 15, np.uint8)
    if lit:
        image[42:58, 85:115] = (40, 200, 255)  # an orange lamp: the max channel counts
    return Frame(image, seq, seq * 40_000_000, seq * 0.04)


def test_pipeline_reads_lit_and_unlit_without_ocr() -> None:
    p = Pipeline(Profile(fields=[LAMP]))
    p._factory = lambda _m: (_ for _ in ()).throw(AssertionError("no OCR for lamps"))  # type: ignore[assignment]
    on = p.process(frame(True, 1)).fields["timeout_h"]
    assert on.status is ReadStatus.VALID and on.text == "TO"
    off = p.process(frame(False, 2), must_read={"timeout_h"}).fields["timeout_h"]
    assert off.status is ReadStatus.VALID and off.text == ""


def test_a_change_needs_a_few_equal_reads_both_ways() -> None:
    p = Pipeline(Profile(fields=[LAMP]))
    logic = FieldLogic(LAMP)
    t = 0
    for lit, expect in [
        (False, ""),
        (False, ""),
        (False, ""),
        (True, ""),
        (True, ""),
        (True, "TO"),
    ]:
        t += 40_000_000
        r = p.process(frame(lit, t), must_read={"timeout_h"}).fields["timeout_h"]
        logic.update(r, t)
        assert logic.text == expect
    # one bad frame (a player passing) doesn't switch it off
    t += 40_000_000
    logic.update(p.process(frame(False, 99), must_read={"timeout_h"}).fields["timeout_h"], t)
    assert logic.text == "TO" and logic.status is FieldStatus.PENDING
