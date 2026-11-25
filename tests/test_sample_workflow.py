"""The real-recording workflow end to end (SPEC 13.3, 15.3): the app records a sample, the
labeler pre-fills ground truth from it, the evaluation runs on it. Uses the real model on a
rendered board (skipped without models)."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from optima_time.config.models import Profile, SourceConfig
from optima_time.fields.formats import ClockStyle
from optima_time.fields.models import BlankPolicy, ClockField, NumberField, Roi
from optima_time.imageio import write_image
from optima_time.recognizers.ppocr import models_dir
from optima_time.runner import Runner
from tools.synth.board import BOXES, COLS, ROWS, Camera, CameraStyle, LedStyle, led_board

pytestmark = pytest.mark.skipif(
    not (models_dir() / "tiny" / "inference.onnx").exists(), reason="models not fetched"
)
ROOT = Path(__file__).resolve().parents[1]


def roi(name: str) -> Roi:
    x, y, w, h = BOXES[name]
    return Roi(x=x / COLS, y=y / ROWS, w=w / COLS, h=h / ROWS)


def test_record_label_evaluate(tmp_path: Path) -> None:
    style, led = CameraStyle(), LedStyle()
    board = led_board({"Time": "07:45", "scoreh": "4", "penaltyh1": ""}, led)
    write_image(str(tmp_path / "hall.png"), Camera(style, board.shape[:2], seed=1).shoot(board, 0))
    profile = Profile(
        source=SourceConfig(path=str(tmp_path / "hall.png")),
        geometry={"corners": [list(c) for c in style.corners]},  # type: ignore[arg-type]
        fields=[
            ClockField(id="Time", roi=roi("Time"), style=ClockStyle.AS_IS),
            NumberField(id="scoreh", roi=roi("scoreh")),
            ClockField(id="penaltyh1", roi=roi("penaltyh1"), blank=BlankPolicy.CLEAR),
        ],
    )
    runner = Runner(profile, None)
    runner.start()
    try:
        folder = runner.recorder.start(runner.profile, 2.0, root=tmp_path / "samples")
        deadline = time.monotonic() + 15
        while not (folder / "profile.json").exists() and time.monotonic() < deadline:
            time.sleep(0.1)
    finally:
        runner.stop()
    assert (folder / "profile.json").exists(), runner.recorder.status

    out = tmp_path / "label"
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.labeler",
            str(folder / "match.mp4"),
            "--profile",
            str(folder / "profile.json"),
            "--out",
            str(out),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, run.stderr
    draft = [json.loads(x) for x in (out / "truth.draft.jsonl").read_text().splitlines()]
    first = {e["field"]: e["value"] for e in draft if e["frame"] == min(d["frame"] for d in draft)}
    assert first.get("Time") == "07:45" and first.get("scoreh") == "4"
    assert (out / "review.html").read_text(encoding="utf-8").count("<tr data-i=") == len(draft)

    (folder / "truth.jsonl").write_text((out / "truth.draft.jsonl").read_text())
    run = subprocess.run(
        [sys.executable, "-m", "tools.eval", str(folder)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, run.stderr
    assert "WRONG PUBLISHED VALUES (app logic): 0" in run.stdout
