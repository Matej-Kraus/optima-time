import time
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from optima_time.api.app import create_app
from optima_time.config.models import Profile, SourceConfig
from optima_time.config.store import load_profile
from optima_time.fields.models import NumberField, Roi
from optima_time.runner import Runner


def make_runner(tmp_path: Path) -> Runner:
    image = np.zeros((90, 160, 3), np.uint8)
    cv2.putText(image, "7", (60, 70), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 230, 20), 6)
    img_path = tmp_path / "board.png"
    cv2.imwrite(str(img_path), image)
    profile = Profile(
        name="t",
        source=SourceConfig(path=str(img_path), speed=1.0),
        fields=[NumberField(id="scoreh", roi=Roi(x=0.25, y=0.1, w=0.5, h=0.8))],
    )

    class Fake:
        name = "fake"

        def read(self, crops):
            from optima_time.recognizers.base import Reading

            return [Reading("7", 0.99, engine="fake") for _ in crops]

    runner = Runner(profile, tmp_path / "t.json")
    runner.pipeline._factory = lambda _m: Fake()  # no model in API tests
    return runner


def wait_for_result(runner: Runner) -> None:
    for _ in range(100):
        if runner.snapshot().result is not None:
            return
        time.sleep(0.02)
    raise AssertionError("no result")


def test_state_frames_and_profile_roundtrip(tmp_path: Path) -> None:
    runner = make_runner(tmp_path)
    runner.start()
    try:
        wait_for_result(runner)
        client = TestClient(create_app(runner, static_dir=tmp_path / "none"))
        state = client.get("/api/state").json()
        assert state["source"]["state"] == "ok"
        assert state["fields"]["scoreh"]["text"] == "7"
        assert client.get("/api/state").headers["cache-control"] == "no-store"

        for view in ("source", "rectified"):
            r = client.get(f"/api/frame.jpg?view={view}")
            assert r.status_code == 200 and r.content[:2] == b"\xff\xd8"
        assert client.get("/api/crop/scoreh.png").status_code == 200

        profile = client.get("/api/profile").json()
        profile["fields"][0]["id"] = "scorea"
        assert client.put("/api/profile", json=profile).status_code == 200
        assert load_profile(tmp_path / "t.json").fields[0].id == "scorea"

        profile["fields"][0]["id"] = "1bad id"
        assert client.put("/api/profile", json=profile).status_code == 422
    finally:
        runner.stop()
