import json
from pathlib import Path

from optima_time.config.models import Profile
from optima_time.fields.models import ClockField, NumberField, Roi
from optima_time.guard import GuardResult, GuardState
from optima_time.outputs.base import OutputHub, OutputWorker
from optima_time.pipeline import FieldRead, FrameResult, ReadStatus
from optima_time.recognizers.base import Reading
from optima_time.state import BoardState

ROI = Roi(x=0, y=0, w=1, h=1)
PROFILE = Profile(fields=[NumberField(id="scoreh", roi=ROI), ClockField(id="Time", roi=ROI)])
OK = GuardResult(GuardState.OK)


class Recorder(OutputWorker):
    def __init__(self) -> None:
        super().__init__()
        self.got: list[dict[str, str]] = []

    def write(self, values: dict[str, str]) -> None:
        self.got.append(values)


def frame(score: str, time_text: str = "05:00") -> FrameResult:
    fields = {}
    for f in PROFILE.fields:
        text = score if f.id == "scoreh" else time_text
        v = f.parse(text, None)
        fields[f.id] = FieldRead(f.id, ReadStatus.VALID, 100, Reading(text, 0.99), v)
    return FrameResult(1, None, 0, 0, fields)


class Clock:
    t = 0

    def __call__(self) -> int:
        self.t += 40_000_000  # 25 fps
        return self.t


CLOCK = Clock()


def make(tmp_path: Path | None = None, initial=None) -> tuple[BoardState, Recorder]:
    rec = Recorder()
    hub = OutputHub([rec])
    hub.start()
    return BoardState(PROFILE, hub, tmp_path, initial), rec


def test_publishes_only_on_change(tmp_path: Path) -> None:
    state, rec = make(tmp_path)
    n0 = len(rec.got) if rec.flush() else 0
    changes = [state.update(frame("3"), OK, True, CLOCK()) for _ in range(15)]
    assert changes.count(True) == 2  # scoreh after 3 reads, Time after 400 ms
    assert rec.flush()
    assert rec.got[-1] == {"scoreh": "3", "Time": "05:00"}
    assert len(rec.got) - n0 <= 2
    log = (tmp_path / next(p.name for p in tmp_path.iterdir())).read_text().splitlines()
    assert {json.loads(x)["kind"] for x in log} == {"changed"}


def test_guard_lost_holds_values_and_logs() -> None:
    state, _ = make()
    for _ in range(15):
        state.update(frame("3"), OK, True, CLOCK())
    for _ in range(100):  # goal animation: the board shows garbage, guard says lost
        assert not state.update(frame("8"), GuardResult(GuardState.LOST, [0.2]), True, CLOCK())
    assert state.values()["scoreh"] == "3"
    assert state.fields()["scoreh"]["status"] == "stale"
    assert [e.kind for e in state.events][-1] == "guard_lost"


def test_source_lost_and_back_rewrites_state() -> None:
    state, rec = make()
    for _ in range(15):
        state.update(frame("3"), OK, True, CLOCK())
    rec.flush()
    n = len(rec.got)
    state.update(None, None, False)
    assert state.fields()["Time"]["status"] == "stale"
    state.update(None, None, True)
    rec.flush()
    assert len(rec.got) == n + 1  # whole state written again when the source returns
    kinds = [e.kind for e in state.events]
    assert kinds[-2:] == ["source_lost", "source_ok"]


def test_initial_values_from_file_prevent_blank_flash() -> None:
    _, rec = make(initial={"scoreh": "2", "Time": "12:00", "gone": "x"})
    rec.flush()
    assert rec.got[0] == {"scoreh": "2", "Time": "12:00"}


def test_hold_release_and_clear() -> None:
    state, _ = make()
    for _ in range(15):
        state.update(frame("3"), OK, True, CLOCK())
    state.hold("scoreh", "4")
    for _ in range(20):
        state.update(frame("3"), OK, True, CLOCK())
    assert state.values()["scoreh"] == "4" and state.fields()["scoreh"]["held"]
    state.clear_values()
    assert state.values() == {"scoreh": "4", "Time": ""}  # held values stay
    state.release("scoreh")
    for _ in range(15):
        state.update(frame("3"), OK, True, CLOCK())
    assert state.values()["scoreh"] == "3"


def test_reconfigure_adds_and_removes_fields() -> None:
    state, _ = make()
    profile = Profile(fields=[NumberField(id="scorea", roi=ROI)])
    state.reconfigure(profile)
    assert set(state.values()) == {"scorea"}
