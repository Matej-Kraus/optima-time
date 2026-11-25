import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from optima_time.api.app import create_app, random_test_values
from optima_time.config.models import OutputsConfig, Profile, SourceConfig, XmlFileOutput
from optima_time.config.store import load_profile
from optima_time.fields.models import ClockField, NumberField, PeriodField, Roi
from optima_time.imageio import write_image
from optima_time.outputs.xml import parse_xml
from optima_time.recognizers.base import Reading
from optima_time.runner import Runner
from tests.xmlread import read_values


class Fake:
    name = "fake"

    def read(self, crops):
        return [Reading("7", 0.99, engine="fake") for _ in crops]


@pytest.fixture
def runner(tmp_path: Path):
    image = np.zeros((90, 160, 3), np.uint8)
    cv2.putText(image, "7", (60, 70), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 230, 20), 6)
    img_path = tmp_path / "board.png"
    write_image(str(img_path), image)
    profile = Profile(
        name="t",
        source=SourceConfig(path=str(img_path), speed=1.0),
        fields=[NumberField(id="scoreh", roi=Roi(x=0.25, y=0.1, w=0.5, h=0.8))],
        outputs=OutputsConfig(xml_file=XmlFileOutput(path=str(tmp_path / "out" / "tabule.xml"))),
    )
    r = Runner(profile, tmp_path / "t.json", log_dir=tmp_path / "logs")
    r.pipeline._factory = lambda _m: Fake()  # no model in API tests
    r.start()
    yield r
    r.stop()


def wait(pred, timeout: float = 3.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


def client(runner: Runner, tmp_path: Path) -> TestClient:
    return TestClient(create_app(runner, static_dir=tmp_path / "none"))


def test_state_frames_and_profile_roundtrip(runner: Runner, tmp_path: Path) -> None:
    c = client(runner, tmp_path)
    wait(lambda: runner.state.values().get("scoreh") == "7")
    state = c.get("/api/state").json()
    assert state["source"]["state"] == "ok"
    assert state["fields"]["scoreh"]["text"] == "7"
    assert state["fields"]["scoreh"]["read_status"] == "valid"
    assert "no-store" in c.get("/api/state").headers["cache-control"]
    for view in ("source", "rectified"):
        r = c.get(f"/api/frame.jpg?view={view}")
        assert r.status_code == 200 and r.content[:2] == b"\xff\xd8"
    assert c.get("/api/crop/scoreh.png").status_code == 200

    profile = c.get("/api/profile").json()
    profile["fields"][0]["id"] = "scorea"
    assert c.put("/api/profile", json=profile).status_code == 200
    assert load_profile(tmp_path / "t.json").fields[0].id == "scorea"
    profile["fields"][0]["id"] = "1bad id"
    assert c.put("/api/profile", json=profile).status_code == 422


def test_xml_file_and_http_data(runner: Runner, tmp_path: Path) -> None:
    c = client(runner, tmp_path)
    xml_path = tmp_path / "out" / "tabule.xml"
    wait(lambda: xml_path.exists() and read_values(xml_path) == {"scoreh": "7"})
    r = c.get("/data/values.xml")
    assert parse_xml(r.content) == {"scoreh": "7"}
    assert "no-store" in r.headers["cache-control"]
    assert c.get("/data/values.json").json() == {"scoreh": "7"}
    assert list((tmp_path / "logs").glob("events-*.jsonl"))


def test_hold_pause_test_data(runner: Runner, tmp_path: Path) -> None:
    c = client(runner, tmp_path)
    xml_path = tmp_path / "out" / "tabule.xml"
    wait(lambda: runner.state.values().get("scoreh") == "7")
    assert c.post("/api/fields/scoreh/hold", json={"text": "5"}).json()["held"]
    wait(lambda: read_values(xml_path) == {"scoreh": "5"})
    c.post("/api/fields/scoreh/release")
    wait(lambda: read_values(xml_path) == {"scoreh": "7"})

    assert c.post("/api/output/pause").json()["mode"] == "paused"
    c.post("/api/fields/scoreh/hold", json={"text": "9"})
    time.sleep(0.2)
    assert read_values(xml_path) == {"scoreh": "7"}  # paused: file unchanged
    c.post("/api/output/test-clear")
    wait(lambda: read_values(xml_path) == {"scoreh": ""})
    c.post("/api/output/live")
    wait(lambda: read_values(xml_path) == {"scoreh": "9"})
    assert c.post("/api/fields/nope/hold", json={"text": "1"}).status_code == 404
    kinds = {e["kind"] for e in c.get("/api/events").json()}
    assert {"changed", "held", "released"} <= kinds


def test_anchor_capture(runner: Runner, tmp_path: Path) -> None:
    c = client(runner, tmp_path)
    wait(lambda: runner.snapshot().rectified is not None)
    roi = {"x": 0.3, "y": 0.1, "w": 0.4, "h": 0.8}
    r = c.post("/api/anchors", json={"roi": roi})
    assert r.status_code == 200 and len(r.json()["guard"]["anchors"]) == 1
    flat = {"x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1}
    assert c.post("/api/anchors", json={"roi": flat}).status_code == 422
    assert c.delete("/api/anchors/0").json()["guard"]["anchors"] == []


def test_test_values_are_valid() -> None:
    roi = Roi(x=0, y=0, w=1, h=1)
    profile = Profile(
        fields=[
            ClockField(id="Time", roi=roi),
            NumberField(id="scoreh", roi=roi),
            PeriodField(id="period", roi=roi),
        ]
    )
    for _ in range(50):
        values = random_test_values(profile)
        assert set(values) == {"Time", "scoreh", "period"}
        assert all(f.parse(values[f.id], None) is not None for f in profile.fields)


def test_auto_anchors_and_editing(runner: Runner, tmp_path: Path) -> None:
    c = client(runner, tmp_path)
    wait(lambda: runner.snapshot().rectified is not None)
    # the test board only has the score digit, which is a field: nothing static is left
    assert c.post("/api/anchors/auto").status_code == 422
    roi = {"x": 0.3, "y": 0.1, "w": 0.4, "h": 0.8}
    assert c.post("/api/anchors", json={"roi": roi}).status_code == 200
    moved = {"x": 0.28, "y": 0.1, "w": 0.42, "h": 0.8}
    r = c.put("/api/anchors/0", json={"roi": moved})
    assert r.status_code == 200 and r.json()["guard"]["anchors"][0]["roi"] == moved
    assert c.put("/api/anchors/5", json={"roi": moved}).status_code == 404


def test_telemetry_otsu_crop_and_guard_history(runner: Runner, tmp_path: Path) -> None:
    c = client(runner, tmp_path)
    wait(lambda: len(runner._arrivals) > 5)
    proc = c.get("/api/state").json()["process"]
    assert proc["frame_ms_p50"] is not None and proc["frame_jitter_ms"] is not None
    r = c.get("/api/crop/scoreh.png?mode=otsu")
    assert r.status_code == 200
    img = np.asarray(cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_GRAYSCALE))
    assert set(np.unique(img).tolist()) <= {0, 255}
    h = c.get("/api/guard/history").json()
    assert h["threshold"] == 0.8 and len(h["points"]) > 0


def test_lock_refuses_setup_changes_but_not_match_controls(runner: Runner, tmp_path: Path) -> None:
    c = client(runner, tmp_path)
    profile = c.get("/api/profile").json()
    assert c.get("/api/state").json()["locked"] is False
    assert c.post("/api/lock", json={"locked": True}).json() == {"locked": True}
    assert c.put("/api/profile", json=profile).status_code == 423
    assert (
        c.post("/api/anchors", json={"roi": {"x": 0, "y": 0, "w": 0.2, "h": 0.2}}).status_code
        == 423
    )
    assert c.post("/api/profiles/save-as", json={"name": "x"}).status_code == 423
    # during a match: holds, output control and test values still work
    assert c.post("/api/fields/scoreh/hold", json={"text": "3"}).status_code == 200
    assert c.post("/api/output/pause").status_code == 200
    assert c.post("/api/output/test").status_code == 200
    state = c.get("/api/state").json()
    assert state["locked"] is True and state["last_test_wall"] > 0
    c.post("/api/lock", json={"locked": False})
    assert c.put("/api/profile", json=profile).status_code == 200
    kinds = [e["kind"] for e in c.get("/api/events?limit=50").json()]
    assert "locked" in kinds and "unlocked" in kinds


def test_alert_conditions_from_a_running_app(runner: Runner) -> None:
    from optima_time.alerts import current_problems

    wait(lambda: runner.state.values().get("scoreh") == "7")
    assert current_problems(runner) == {
        "source": False,
        "output": False,
        "stuck": False,
        "guard": False,
    }


def test_output_delay_from_the_profile(runner: Runner, tmp_path: Path) -> None:
    c = client(runner, tmp_path)
    p = c.get("/api/profile").json()
    assert p["outputs"]["delay_ms"] == 0
    p["outputs"]["delay_ms"] = 1500
    assert c.put("/api/profile", json=p).status_code == 200
    assert runner.hub.delay_s == 1.5
    p["source"] |= {"type": "stream", "url": "udp://0.0.0.0:59999"}
    assert c.put("/api/profile", json=p).json()["source"]["url"] == "udp://0.0.0.0:59999"


def test_derived_fields_and_http_feed_follow_the_output(runner: Runner, tmp_path: Path) -> None:
    c = client(runner, tmp_path)
    wait(lambda: runner.state.values().get("scoreh") == "7")
    p = c.get("/api/profile").json()
    p["derived"] = [{"id": "skore", "template": "{scoreh} góly"}]
    assert c.put("/api/profile", json=p).status_code == 200
    wait(lambda: c.get("/api/state").json()["derived"].get("skore") == "7 góly")
    assert parse_xml(c.get("/data/values.xml").content)["skore"] == "7 góly"
    bad = p | {"derived": [{"id": "x", "template": "{nope}"}]}
    assert c.put("/api/profile", json=bad).status_code == 422
    # the HTTP feed shows what vMix gets: test data, not the live value
    c.post("/api/output/test")
    assert c.get("/data/values.json").json()["skore"].endswith(" góly")
    c.post("/api/output/test-clear")
    assert c.get("/data/values.json").json() == {"scoreh": "", "skore": ""}
    c.post("/api/output/live")
    assert c.get("/data/values.json").json()["skore"] == "7 góly"
