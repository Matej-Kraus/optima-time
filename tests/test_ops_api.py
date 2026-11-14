"""Milestone 4 API: profiles, samples, diagnostics, preview, PIN."""

import io
import json
import time
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from optima_time.api.app import create_app
from optima_time.config import profiles
from optima_time.config.models import Profile, SourceConfig
from optima_time.config.store import load_profile, save_profile
from optima_time.fields.models import NumberField, Roi
from optima_time.recognizers.base import Reading
from optima_time.runner import Runner


class Fake:
    name = "fake"

    def read(self, crops):
        return [Reading("7", 0.99, engine="fake") for _ in crops]


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OPTIMA_TIME_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture
def runner(tmp_path: Path, home: Path):
    image = np.zeros((90, 160, 3), np.uint8)
    cv2.putText(image, "7", (60, 70), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 230, 20), 6)
    cv2.imwrite(str(tmp_path / "b.png"), image)
    profile = Profile(
        name="hala",
        source=SourceConfig(path=str(tmp_path / "b.png")),
        fields=[NumberField(id="scoreh", roi=Roi(x=0.25, y=0.1, w=0.5, h=0.8))],
    )
    path = profiles.profiles_dir() / "hala.json"
    save_profile(profile, path)
    r = Runner(profile, path, log_dir=home / "logs")
    r.pipeline._factory = lambda _m: Fake()
    r.start()
    yield r
    r.stop()


def wait(pred, timeout: float = 5.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


def test_profiles_save_as_load_export_import(runner: Runner, tmp_path: Path) -> None:
    c = TestClient(create_app(runner, static_dir=tmp_path / "none"))
    assert c.get("/api/profiles").json()["current"]["name"] == "hala"
    assert c.post("/api/profiles/save-as", json={"name": "Hala Ostrava"}).status_code == 200
    assert runner.profile.name == "Hala-Ostrava"
    assert c.post("/api/profiles/save-as", json={"name": "Hala Ostrava"}).status_code == 409
    names = [p["name"] for p in c.get("/api/profiles").json()["profiles"]]
    assert names == ["Hala-Ostrava", "hala"]
    assert c.post("/api/profiles/load", json={"name": "hala"}).json()["name"] == "hala"
    exported = c.get("/api/profiles/export")
    assert "attachment" in exported.headers["content-disposition"]
    data = json.loads(exported.content)
    r = c.post("/api/profiles/import", json={"name": "z-exportu", "profile": data})
    assert r.status_code == 200 and runner.profile.name == "z-exportu"
    bad = c.post("/api/profiles/import", json={"name": "x", "profile": {"fields": [{"id": "1"}]}})
    assert bad.status_code == 422
    assert c.post("/api/profiles/load", json={"name": "nope"}).status_code == 404


def test_sample_recording(runner: Runner, tmp_path: Path) -> None:
    c = TestClient(create_app(runner, static_dir=tmp_path / "none"))
    folder = Path(c.post("/api/samples/record", json={"seconds": 0.6}).json()["folder"])
    assert c.post("/api/samples/record", json={"seconds": 1}).status_code == 409
    wait(lambda: (folder / "profile.json").exists())
    assert (folder / "match.mp4").stat().st_size > 0
    lines = (folder / "readings.jsonl").read_text().splitlines()
    assert len(lines) >= 5 and "scoreh" in json.loads(lines[0])["fields"]
    sample = load_profile(folder / "profile.json")
    assert sample.geometry.corners[2] == (1.0, 1.0)
    assert Path(sample.source.path).name == "match.mp4"


def test_diagnostics_zip(runner: Runner, tmp_path: Path) -> None:
    c = TestClient(create_app(runner, static_dir=tmp_path / "none"))
    wait(lambda: runner.snapshot().result is not None)
    z = zipfile.ZipFile(io.BytesIO(c.get("/api/diagnostics.zip").content))
    names = set(z.namelist())
    assert {
        "versions.json",
        "profile.json",
        "state.json",
        "events.json",
        "source.jpg",
        "rectified.png",
        "crops/scoreh.png",
    } <= names


def test_pin_protects_remote_access(runner: Runner, tmp_path: Path) -> None:
    app = create_app(runner, static_dir=tmp_path / "none", pin="4321")
    local = TestClient(app)  # "testclient" counts as local
    assert local.get("/api/state").status_code == 200
    remote = TestClient(app, client=("192.168.1.20", 5000))
    assert remote.get("/api/state").status_code == 401
    assert remote.get("/data/values.xml").status_code == 401
    assert remote.get("/login?pin=0000").status_code == 401
    ok = remote.get("/login?pin=4321", follow_redirects=False)
    assert ok.status_code == 303
    assert remote.get("/api/state").status_code == 200  # cookie set


def test_profile_name_resolution(home: Path) -> None:
    assert profiles.resolve("hala") == profiles.profiles_dir() / "hala.json"
    assert profiles.resolve("x/y.json") == Path("x/y.json")
    assert profiles.safe_name(" Hala  Bratislava ") == "Hala-Bratislava"
    with pytest.raises(ValueError):
        profiles.safe_name("../")
