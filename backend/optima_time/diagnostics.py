"""Diagnostic bundle (SPEC 13.3): everything needed to understand a problem, in one ZIP.

source.jpg, rectified.jpg, crops/<field>.png, profile.json, state.json, events.json,
the latest event-log and application-log files, versions.json.
"""

from __future__ import annotations

import io
import json
import platform
import time
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import cv2

from optima_time import __version__

if TYPE_CHECKING:
    from optima_time.runner import Runner

MAX_LOG_BYTES = 5 * 2**20


def _versions() -> dict:
    import numpy
    import onnxruntime

    return {
        "optima_time": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "opencv": cv2.__version__,
        "numpy": numpy.__version__,
        "onnxruntime": onnxruntime.__version__,
    }


def _tail(path: Path) -> bytes:
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > MAX_LOG_BYTES:
            f.seek(size - MAX_LOG_BYTES)
        return f.read()


def build_zip(runner: Runner, log_dir: Path | None) -> bytes:
    snap = runner.snapshot()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("versions.json", json.dumps(_versions(), indent=1))
        z.writestr("profile.json", runner.profile.model_dump_json(indent=2))
        state = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "values": runner.state.values(),
            "fields": runner.state.fields(),
            "source": runner.source_status(),
            "outputs": runner.outputs_status(),
            "process": runner.process_status(),
            "timings_ms": snap.result.timings_ms if snap.result else None,
            "guard": asdict(snap.result.guard) if snap.result else None,
        }
        z.writestr("state.json", json.dumps(state, indent=1, ensure_ascii=False, default=str))
        z.writestr(
            "events.json",
            json.dumps([asdict(e) for e in runner.state.events], indent=1, ensure_ascii=False),
        )
        if snap.frame is not None:
            ok, data = cv2.imencode(".jpg", snap.frame.image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if ok:
                z.writestr("source.jpg", data.tobytes())
        if snap.rectified is not None:
            ok, data = cv2.imencode(".png", snap.rectified)
            if ok:
                z.writestr("rectified.png", data.tobytes())
        if snap.result is not None:
            for fid, r in snap.result.fields.items():
                if r.crop is not None:
                    ok, data = cv2.imencode(".png", r.crop)
                    if ok:
                        z.writestr(f"crops/{fid}.png", data.tobytes())
        if log_dir is not None and log_dir.is_dir():
            for pattern in ("events-*.jsonl", "app.log"):
                files = sorted(log_dir.glob(pattern))
                if files:
                    z.writestr(f"logs/{files[-1].name}", _tail(files[-1]))
    return buf.getvalue()
