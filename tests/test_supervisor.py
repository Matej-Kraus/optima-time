import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from optima_time.config.models import OutputsConfig, Profile, SourceConfig, XmlFileOutput
from optima_time.fields.models import NumberField, Roi
from optima_time.imageio import write_image
from optima_time.recognizers.base import Reading
from optima_time.runner import Runner
from tests.xmlread import read_bytes

pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")


class Fatal(BaseException):
    """Escapes `except Exception`: kills the thread like a real bug would."""


class Fake:
    name = "fake"

    def read(self, crops):
        return [Reading("7", 0.99, engine="fake") for _ in crops]


def make_runner(tmp_path: Path) -> Runner:
    image = np.zeros((90, 160, 3), np.uint8)
    cv2.putText(image, "7", (60, 70), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 230, 20), 6)
    write_image(str(tmp_path / "b.png"), image)
    profile = Profile(
        source=SourceConfig(path=str(tmp_path / "b.png")),
        fields=[NumberField(id="scoreh", roi=Roi(x=0.25, y=0.1, w=0.5, h=0.8))],
        outputs=OutputsConfig(xml_file=XmlFileOutput(path=str(tmp_path / "t.xml"))),
    )
    r = Runner(profile, None)
    r.pipeline._factory = lambda _m: Fake()
    return r


def wait(pred, timeout: float = 3.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


def test_dead_pipeline_thread_is_restarted(tmp_path: Path) -> None:
    r = make_runner(tmp_path)
    r.start()
    try:
        original = r.pipeline.process
        calls = {"n": 0}

        def boom(*a, **kw):
            calls["n"] += 1
            if calls["n"] == 3:
                raise Fatal()
            return original(*a, **kw)

        r.pipeline.process = boom  # type: ignore[method-assign]
        wait(lambda: not r.pipeline_alive())
        r.supervisor.check()
        assert r.pipeline_alive() and r.supervisor.restarts == 1
        wait(lambda: calls["n"] > 10)  # processing again
        assert any(e.kind == "thread_restarted" for e in r.state.events)
    finally:
        r.stop()


def test_dead_output_thread_is_restarted(tmp_path: Path) -> None:
    r = make_runner(tmp_path)
    r.start()
    try:
        w = r.hub.workers[0]
        wait(lambda: (tmp_path / "t.xml").exists())
        original = w.write

        def boom(values):
            raise Fatal()

        w.write = boom  # type: ignore[method-assign]
        w.submit({"scoreh": "1"})
        wait(lambda: not w.alive())
        w.write = original  # type: ignore[method-assign]
        r.supervisor.check()
        assert w.alive()
        r.state.hold("scoreh", "5")
        wait(lambda: b"<scoreh>5</scoreh>" in read_bytes(tmp_path / "t.xml"))
    finally:
        r.stop()


def test_process_status(tmp_path: Path) -> None:
    r = make_runner(tmp_path)
    status = r.process_status()
    assert status["rss_mb"] > 10 and status["threads"] >= 1
