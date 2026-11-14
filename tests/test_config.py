import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from optima_time.config.models import Profile
from optima_time.config.store import load_profile, save_profile
from optima_time.fields.formats import ClockStyle
from optima_time.fields.models import BlankPolicy, ClockField, NumberField, PeriodField, Roi

ROI = Roi(x=0.1, y=0.1, w=0.2, h=0.1)


def sample_profile() -> Profile:
    return Profile(
        name="hala",
        fields=[
            ClockField(id="Time", roi=ROI, tenths=True, style=ClockStyle.NO_LEADING_ZERO),
            NumberField(id="scoreh", roi=ROI),
            PeriodField(id="period", roi=ROI),
            ClockField(id="penaltyh1", roi=ROI, blank=BlankPolicy.CLEAR),
        ],
    )


def test_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    profile = sample_profile()
    save_profile(profile, path)
    assert load_profile(path) == profile
    assert not list(tmp_path.glob(".*tmp"))  # no temp files left


def test_discriminated_fields_from_json() -> None:
    data = json.loads(sample_profile().model_dump_json())
    fields = Profile.model_validate(data).fields
    assert [type(f) for f in fields] == [ClockField, NumberField, PeriodField, ClockField]


@pytest.mark.parametrize("bad_id", ["1score", "score h", "", "skóre"])
def test_field_id_must_be_xml_name(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        NumberField(id=bad_id, roi=ROI)


def test_field_ids_unique() -> None:
    with pytest.raises(ValidationError):
        Profile(fields=[NumberField(id="a", roi=ROI), NumberField(id="a", roi=ROI)])


def test_roi_must_stay_inside() -> None:
    with pytest.raises(ValidationError):
        Roi(x=0.9, y=0.0, w=0.2, h=0.1)


def test_broken_file_is_backed_up(tmp_path: Path) -> None:
    path = tmp_path / "hala.json"
    path.write_text("{ not json", encoding="utf-8")
    profile = load_profile(path)
    assert profile == Profile(name="hala")
    assert not path.exists()
    assert len(list(tmp_path.glob("hala.broken-*.json"))) == 1


def test_future_schema_version_is_rejected_safely(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    assert load_profile(path) == Profile(name="p")
