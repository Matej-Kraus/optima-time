import os
import threading
import time
from pathlib import Path

from optima_time.outputs.base import OutputHub, OutputMode, OutputWorker
from optima_time.outputs.xml import build_xml, parse_xml
from optima_time.outputs.xml_file import XmlFileWorker
from tests.xmlread import read_values

VALUES = {"Time": "12:45", "penaltya1": "", "penaltyh1": "1:32", "scoreh": "2", "scorea": "1"}


def test_xml_shape_matches_production() -> None:
    xml = build_xml(VALUES, "\n").decode("utf-8")
    assert xml == (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<root>\n"
        "  <Time>12:45</Time>\n"  # ordinal order: uppercase first, as in today's file
        "  <penaltya1/>\n"
        "  <penaltyh1>1:32</penaltyh1>\n"
        "  <scorea>1</scorea>\n"
        "  <scoreh>2</scoreh>\n"
        "</root>\n"
    )


def test_xml_crlf_and_escaping_roundtrip() -> None:
    data = build_xml({"a": "<&>\"'", "b": ""})
    assert b"\r\n" in data
    assert parse_xml(data) == {"a": "<&>\"'", "b": ""}


def test_xml_file_worker_writes_atomically(tmp_path: Path) -> None:
    path = tmp_path / "out" / "tabule.xml"
    w = XmlFileWorker(path)
    w.start()
    w.submit(VALUES)
    assert w.flush()
    assert read_values(path) == VALUES
    assert w.status.ok and w.status.writes == 1
    assert [p.name for p in path.parent.iterdir()] == ["tabule.xml"]  # no temp files left
    w.stop()


class LockedReplace:
    """os.replace that fails like Windows while a reader holds the target open."""

    def __init__(self, locked_for_s: float) -> None:
        self.until = time.monotonic() + locked_for_s
        self.calls = 0

    def __call__(self, src: str, dst: str) -> None:
        self.calls += 1
        if time.monotonic() < self.until:
            raise PermissionError(13, "The process cannot access the file")
        os.replace(src, dst)


def test_retries_while_target_is_locked(tmp_path: Path) -> None:
    path = tmp_path / "t.xml"
    replace = LockedReplace(0.1)
    w = XmlFileWorker(path, replace=replace)
    w.start()
    w.submit(VALUES)
    assert w.flush()
    assert read_values(path) == VALUES
    assert replace.calls >= 2  # retried (how often depends on the machine's timer)
    assert w.status.slow_writes == 0  # 100 ms < 250 ms
    w.stop()


def test_newer_values_win_while_locked(tmp_path: Path) -> None:
    path = tmp_path / "t.xml"
    w = XmlFileWorker(path, replace=LockedReplace(0.15))
    w.start()
    w.submit({"Time": "1:00"})
    time.sleep(0.05)
    w.submit({"Time": "0:59"})
    assert w.flush()
    assert read_values(path) == {"Time": "0:59"}
    w.stop()


def test_slow_write_is_reported(tmp_path: Path) -> None:
    w = XmlFileWorker(tmp_path / "t.xml", replace=LockedReplace(0.3))
    w.start()
    w.submit(VALUES)
    assert w.flush()
    assert w.status.slow_writes == 1 and w.status.message.startswith("slow write")
    w.stop()


def test_read_existing(tmp_path: Path) -> None:
    path = tmp_path / "t.xml"
    path.write_bytes(build_xml(VALUES))
    assert XmlFileWorker(path).read_existing() == VALUES
    assert XmlFileWorker(tmp_path / "missing.xml").read_existing() == {}
    (tmp_path / "bad.xml").write_text("<not xml")
    assert XmlFileWorker(tmp_path / "bad.xml").read_existing() == {}


class Recorder(OutputWorker):
    name = "rec"

    def __init__(self, fail_times: int = 0) -> None:
        super().__init__()
        self.got: list[dict[str, str]] = []
        self.fail_times = fail_times

    def write(self, values: dict[str, str]) -> None:
        if self.fail_times:
            self.fail_times -= 1
            raise OSError("disk gone")
        self.got.append(values)


def test_worker_keeps_only_latest_and_recovers_from_errors() -> None:
    gate = threading.Event()

    class Slow(Recorder):
        def write(self, values: dict[str, str]) -> None:
            gate.wait()
            super().write(values)

    w = Slow()
    w.start()
    for i in range(50):
        w.submit({"n": str(i)})
    gate.set()
    assert w.flush()
    assert w.got[-1] == {"n": "49"} and len(w.got) <= 2
    w.stop()

    w2 = Recorder(fail_times=2)
    w2.start()
    w2.submit({"n": "1"})
    assert w2.flush()
    assert w2.got == [{"n": "1"}] and w2.status.failures == 2 and w2.status.ok
    w2.stop()


def test_hub_pause_test_and_resume() -> None:
    rec = Recorder()
    hub = OutputHub([rec])
    hub.start()
    hub.publish({"a": "1"})
    assert rec.flush()
    hub.set_mode(OutputMode.PAUSED)
    hub.publish({"a": "2"})
    assert rec.flush() and rec.got[-1] == {"a": "1"}  # paused: graphic keeps 1
    hub.write_test({"a": "88"})
    assert rec.flush() and rec.got[-1] == {"a": "88"} and hub.mode is OutputMode.TEST
    hub.publish({"a": "3"})
    assert rec.flush() and rec.got[-1] == {"a": "88"}  # test data stays
    hub.set_mode(OutputMode.LIVE)
    assert rec.flush() and rec.got[-1] == {"a": "3"}  # catches up at once
    hub.stop()
