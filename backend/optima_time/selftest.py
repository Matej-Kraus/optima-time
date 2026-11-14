"""`optima-time --self-test`: check the installation without the UI (SPEC 14.2).

Each check prints OK or CHYBA with a reason. Exit code 0 only if every required check passed.
Optional checks (NDI, capture devices) only warn: a PC may legitimately have none.
"""

from __future__ import annotations

import platform
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from pathlib import Path

import numpy as np

from optima_time import __version__


def _models() -> str:
    from optima_time.recognizers.ppocr import models_dir

    out = []
    for name in ("tiny", "small"):
        if not (models_dir() / name / "inference.onnx").exists():
            if name == "tiny":
                raise FileNotFoundError(f"model tiny chybí v {models_dir()}")
            out.append("small chybí (volitelný)")
            continue
        out.append(f"{name} ok")
    return ", ".join(out) + f" ({models_dir()})"


def _recognition() -> str:
    """Read a rendered clock and score with the bundled model: the whole OCR chain works."""
    import cv2

    from optima_time.recognizers.base import Crop
    from optima_time.recognizers.ppocr import PPOCRRecognizer

    rec = PPOCRRecognizer("tiny", threads=1)
    clock = np.zeros((70, 240, 3), np.uint8)
    cv2.putText(clock, "12:34", (8, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (40, 255, 40), 5)
    score = np.zeros((70, 70, 3), np.uint8)
    cv2.putText(score, "7", (14, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 230, 20), 5)
    t0 = time.perf_counter()
    got = [
        r.text for r in rec.read([Crop(clock, "0123456789:.", 160), Crop(score, "0123456789", 160)])
    ]
    ms = (time.perf_counter() - t0) * 1000
    if got != ["12:34", "7"]:
        raise ValueError(f"přečteno {got}, čekáno ['12:34', '7']")
    return f"12:34 a 7 přečteny za {ms:.0f} ms"


def _onnxruntime() -> str:
    import onnxruntime as ort

    providers = ort.get_available_providers()
    if "CPUExecutionProvider" not in providers:
        raise RuntimeError(f"chybí CPUExecutionProvider ({providers})")
    return f"{ort.__version__}, CPU"


def _opencv() -> str:
    import cv2

    ok, _ = cv2.imencode(".jpg", np.zeros((8, 8, 3), np.uint8))
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return cv2.__version__


def _ndi() -> str:
    from optima_time.sources.ndi import list_ndi_sources

    names = list_ndi_sources(wait_s=2.0)
    return f"knihovna ok, zdrojů v síti: {len(names)}" + (
        f" ({', '.join(names[:3])})" if names else ""
    )


def _devices() -> str:
    from optima_time.sources.device import list_devices

    devs = list_devices()
    return f"{len(devs)}: " + ", ".join(d.name for d in devs[:5]) if devs else "žádné"


def _frontend() -> str:
    from optima_time.api.app import frontend_dir

    index = frontend_dir() / "index.html"
    if not index.exists():
        raise FileNotFoundError(f"chybí {index} (npm run build)")
    return str(frontend_dir())


def _folders() -> str:
    from optima_time.config.profiles import profiles_dir
    from optima_time.config.store import app_dir, write_atomic
    from optima_time.recorder import samples_dir

    for folder in (profiles_dir(), app_dir() / "logs", samples_dir()):
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".selftest"
        write_atomic(probe, b"ok")
        probe.unlink()
    return str(app_dir())


def _xml_write() -> str:
    from optima_time.outputs.xml import parse_xml
    from optima_time.outputs.xml_file import XmlFileWorker

    with tempfile.TemporaryDirectory() as tmp:
        w = XmlFileWorker(Path(tmp) / "t.xml")
        w.write({"Time": "1:00", "scoreh": ""})
        if parse_xml((Path(tmp) / "t.xml").read_bytes()) != {"Time": "1:00", "scoreh": ""}:
            raise ValueError("XML nesedí")
    return "atomický zápis ok"


CHECKS: list[tuple[str, Callable[[], str], bool]] = [
    ("Modely PP-OCR", _models, True),
    ("ONNX Runtime", _onnxruntime, True),
    ("OpenCV", _opencv, True),
    ("Rozpoznávání", _recognition, True),
    ("Zápis XML", _xml_write, True),
    ("Složky aplikace", _folders, True),
    ("Webové UI", _frontend, True),
    ("NDI", _ndi, False),
    ("Capture zařízení", _devices, False),
]


def run_self_test(out=print) -> int:
    out(f"Optima Time {__version__}: kontrola instalace")
    out(
        f"{platform.platform()}, Python {platform.python_version()}, "
        f"{'zabalená verze' if getattr(sys, 'frozen', False) else 'ze zdrojů'}"
    )
    failed = 0
    for name, check, required in CHECKS:
        try:
            detail = check()
            out(f"  OK     {name}: {detail}")
        except Exception as error:
            if required:
                failed += 1
                out(f"  CHYBA  {name}: {error}")
                out("         " + traceback.format_exc().strip().splitlines()[-1])
            else:
                out(f"  POZOR  {name}: {error}")
    out("Výsledek: " + ("vše v pořádku" if not failed else f"{failed} chyb"))
    return 0 if not failed else 1
