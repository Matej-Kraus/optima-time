import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from optima_time.config.models import Profile
from optima_time.config.store import load_profile, parse_profile, save_profile
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


def test_xml_output_names_are_valid_known_and_unique() -> None:
    data = sample_profile().model_dump(mode="json")
    data["outputs"]["xml_file"]["names"] = {"Time": "Clock", "scoreh": "HomeScore"}
    assert Profile.model_validate(data).outputs.xml_file.names["Time"] == "Clock"

    data["outputs"]["xml_file"]["names"] = {"missing": "Clock"}
    with pytest.raises(ValidationError, match="neexistující pole"):
        Profile.model_validate(data)

    data["outputs"]["xml_file"]["names"] = {"Time": "scoreh"}
    with pytest.raises(ValidationError, match="jedinečné"):
        Profile.model_validate(data)

    data["outputs"]["xml_file"]["names"] = {"Time": "not an xml name"}
    with pytest.raises(ValidationError):
        Profile.model_validate(data)


def test_version_one_profile_migrates_without_changing_behaviour() -> None:
    data = sample_profile().model_dump(mode="json")
    data["schema_version"] = 1
    data["outputs"]["xml_file"].pop("names")
    for field in data["fields"]:
        field.pop("zero_is_blank", None)
    profile = parse_profile(data)
    assert profile.schema_version == 2
    assert profile.outputs.xml_file.names == {}
    penalty = next(f for f in profile.fields if f.id == "penaltyh1")
    assert isinstance(penalty, ClockField) and not penalty.zero_is_blank


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


def test_profile_accepts_what_the_ui_sends() -> None:
    data = json.loads(sample_profile().model_dump_json())
    data["geometry"]["rotate"] = 90
    data["preprocess"] = {"blend_frames": 3, "blend_mode": "mean"}
    data["detection"] = {"enabled": False, "threshold": 0.2, "max_age_ms": 500}
    data["outputs"]["xml_file"] |= {"newline": "lf", "clear_on_exit": True}
    data["fields"][0] |= {"direction": "down", "align": "right", "align_width": 5}
    data["fields"][2]["names"] = {"1": "1. tretina", "4": "predĺženie"}  # JSON keys are strings
    p = Profile.model_validate(data)
    assert p.geometry.rotate == 90 and p.preprocess.blend_frames == 3
    period = p.fields[2]
    assert isinstance(period, PeriodField) and period.names == {1: "1. tretina", 4: "predĺženie"}
    value = period.parse("4", None)
    assert value is not None and period.render(value) == "predĺženie"
    clock = p.fields[0]
    assert isinstance(clock, ClockField)
    v = clock.parse("5:13", None)
    assert v is not None and clock.render(v) == " 5:13"
