import pytest

from optima_time.config.models import DerivedField, Profile
from optima_time.fields.models import ClockField, NumberField, PeriodField, Roi
from optima_time.fields.template import Template, TemplateError, check_template
from optima_time.outputs.base import OutputHub
from optima_time.state import BoardState

V = {"scoreh": "2", "scorea": "10", "period": "4", "Time": "07:45", "penaltyh1": ""}


def r(src: str, values: dict[str, str] = V) -> str:
    return Template(src).render(values)


def test_placeholders_and_literals() -> None:
    assert r("{scoreh} : {scorea}") == "2 : 10"
    assert r("{{scoreh}}") == "{scoreh}"
    assert r("bez polí") == "bez polí"
    assert r("{missing}") == ""


def test_filters() -> None:
    assert r("{penaltyh1|if:1;0}") == "0"
    assert r("{scoreh|if:1;0}") == "1"
    assert r("{penaltyh1|default:—}") == "—"
    assert r("{period|map:1=1. třetina;2=2. třetina;*=Prodloužení}") == "Prodloužení"
    assert r("{period|map:1=a;2=b}") == "4"  # no match, no fallback: the value
    assert r("{scoreh|map:2=C:\\gfx\\2.png}") == "C:\\gfx\\2.png"
    assert r("{scoreh|pad:2}") == "02"
    assert r("{Time|nolead}") == "7:45"
    assert r("{Time|nolead}", {"Time": "00:42"}) == "0:42"
    assert r("{penaltyh1|pad:2|default:-}") == "-"
    assert r("{scorea|upper}") == "10"


def test_aggregates() -> None:
    values = {"penaltyh1": "1:12", "penaltyh2": "", "foul1": "1", "foul2": "0", "foul3": "1"}
    assert r("{count:penaltyh1,penaltyh2}", values) == "1"
    assert r("{count:penaltyh1, penaltyh2}", {}) == "0"
    assert r("{count:foul1,foul2,foul3}", values) == "2"  # "0" is off
    assert r("{sum:foul1,foul2,foul3}", values) == "2"
    assert r("{sum:scoreh,scorea,Time}") == "12"  # not a whole number counts 0
    assert r("{count:penaltyh1,penaltyh2|map:0=;*=PP}", values) == "PP"
    assert r("{sum:foul1|pad:2}", values) == "01"
    assert Template("{count:a,b} {c}").names == {"a", "b", "c"}
    with pytest.raises(TemplateError):
        check_template("{count:scoreh,shots}", {"scoreh"})
    with pytest.raises(TemplateError):
        Template("{count:a,}")


def test_errors() -> None:
    with pytest.raises(TemplateError):
        Template("{scoreh|nope}")
    with pytest.raises(TemplateError):
        Template("{score h}")
    with pytest.raises(TemplateError):
        Template("{scoreh")
    with pytest.raises(TemplateError):
        check_template("{scoreh|pad:x}", {"scoreh"})
    with pytest.raises(TemplateError):
        check_template("{shots}", {"scoreh"})


ROI = Roi(x=0, y=0, w=0.2, h=0.2)
FIELDS = [
    ClockField(id="Time", roi=ROI),
    NumberField(id="scoreh", roi=ROI),
    NumberField(id="scorea", roi=ROI),
    PeriodField(id="period", roi=ROI),
]


def test_profile_validates_derived_fields() -> None:
    p = Profile(fields=FIELDS, derived=[DerivedField(id="skore", template="{scoreh}:{scorea}")])
    assert p.derived[0].id == "skore"
    with pytest.raises(ValueError, match="neexistující"):
        Profile(fields=FIELDS, derived=[DerivedField(id="x", template="{shots}")])
    with pytest.raises(ValueError, match="jiné pole"):
        Profile(fields=FIELDS, derived=[DerivedField(id="scoreh", template="{scorea}")])


def test_board_state_publishes_derived_values() -> None:
    profile = Profile(
        fields=FIELDS,
        derived=[
            DerivedField(id="skore", template="{scoreh|default:0} : {scorea|default:0}"),
            DerivedField(id="off", template="{Time}", enabled=False),
        ],
    )
    hub = OutputHub()
    state = BoardState(profile, hub, initial={"scoreh": "3", "scorea": "1"})
    out = state.output_values()
    assert out["skore"] == "3 : 1" and "off" not in out
    assert hub.sent["skore"] == "3 : 1"  # what the workers and the HTTP feed get
