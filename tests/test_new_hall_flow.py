"""The OPERATOR.md "new hall" procedure end to end, through the same API the UI uses:
empty profile -> source -> corners -> fields -> anchors -> XML path -> the right values in the
XML file. Uses the real PP-OCR model (skipped without models) on a rendered board."""

import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from optima_time.api.app import create_app
from optima_time.config.models import Profile
from optima_time.recognizers.ppocr import models_dir
from optima_time.runner import Runner
from tests.xmlread import read_values
from tools.synth.board import BOXES, COLS, LABELS, ROWS, Camera, CameraStyle, LedStyle, led_board

pytestmark = pytest.mark.skipif(
    not (models_dir() / "tiny" / "inference.onnx").exists(), reason="models not fetched"
)

BOARD = {
    "Time": "12:34",
    "period": "2",
    "scoreh": "10",
    "scorea": "3",
    "penaltyh1": "1:45",
    "penaltyh2": "",
    "penaltya1": "",
    "penaltya2": "",
}
EXPECTED = {
    "Time": "12:34",
    "period": "2",
    "scoreh": "10",
    "scorea": "3",
    "penaltyh1": "1:45",
    "penaltyh2": "",
    "penaltya1": "",
    "penaltya2": "",
}


def roi(box: tuple[int, int, int, int]) -> dict:
    x, y, w, h = box
    return {"x": x / COLS, "y": y / ROWS, "w": w / COLS, "h": h / ROWS}


def test_new_hall_setup_through_the_api(tmp_path: Path) -> None:
    led, style = LedStyle(), CameraStyle()
    board = led_board(BOARD, led)
    frame = Camera(style, board.shape[:2], seed=3).shoot(board, 1)
    cv2.imwrite(str(tmp_path / "hall.png"), frame)

    runner = Runner(Profile(name="nova-hala"), tmp_path / "nova-hala.json")
    runner.start()
    c = TestClient(create_app(runner, static_dir=tmp_path / "none"))
    try:
        p = c.get("/api/profile").json()
        # 4. source
        p["source"] = p["source"] | {"type": "file", "path": str(tmp_path / "hall.png")}
        p = c.put("/api/profile", json=p).json()
        # 5. corners
        p["geometry"]["corners"] = [list(xy) for xy in style.corners]
        p = c.put("/api/profile", json=p).json()
        # 6. fields
        kinds = {"Time": "clock", "period": "period", "scoreh": "number", "scorea": "number"}
        for fid, box in BOXES.items():
            field = {
                "id": fid,
                "label": "",
                "type": kinds.get(fid, "clock"),
                "roi": roi(box),
                "enabled": True,
            }
            if fid == "Time":
                field |= {"tenths": True, "style": "no_leading_zero"}
            if fid.startswith("penalty"):
                field |= {"blank": "clear"}
            p["fields"].append(field)
        p = c.put("/api/profile", json=p).json()
        # 7. anchors (captured from the live frame)
        deadline = time.monotonic() + 5
        while runner.snapshot().rectified is None and time.monotonic() < deadline:
            time.sleep(0.05)
        for box in LABELS.values():
            assert c.post("/api/anchors", json={"roi": roi(box)}).status_code == 200
        # 8. output
        p = c.get("/api/profile").json()
        p["outputs"]["xml_file"]["path"] = str(tmp_path / "vmix" / "tabule.xml")
        c.put("/api/profile", json=p)

        xml = tmp_path / "vmix" / "tabule.xml"
        deadline = time.monotonic() + 30
        values: dict = {}
        state: dict = {}
        while time.monotonic() < deadline:  # a loaded machine needs longer (assert behaviour)
            if xml.exists():
                values = read_values(xml)
                state = c.get("/api/state").json()
                if values == EXPECTED and state["guard"]["state"] == "ok":
                    break
            time.sleep(0.1)
        assert values == EXPECTED
        assert state["guard"]["state"] == "ok"
        assert state["outputs"]["workers"]["xml_file"]["ok"] is True
        saved = (tmp_path / "nova-hala.json").read_text()
        assert '"scoreh"' in saved and '"template"' in saved  # everything autosaved
    finally:
        runner.stop()


def test_image_is_realistic_enough() -> None:
    """Sanity: the rendered hall frame isn't blank (guards against a broken synth)."""
    led = LedStyle()
    board = led_board(BOARD, led)
    frame = Camera(CameraStyle(), board.shape[:2], seed=3).shoot(board, 1)
    assert frame.shape == (1080, 1920, 3) and float(np.asarray(frame).std()) > 10
