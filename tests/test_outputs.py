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


def test_xml_file_worker_maps_external_names_both_ways(tmp_path: Path) -> None:
    path = tmp_path / "mapped.xml"
    worker = XmlFileWorker(path, names={"Time": "Clock", "scoreh": "HomeScore"})
    worker.write({"Time": "12:45", "scoreh": "2", "period": "1"})
    assert parse_xml(path.read_bytes()) == {"Clock": "12:45", "HomeScore": "2", "period": "1"}
    assert worker.read_existing() == {"Time": "12:45", "scoreh": "2", "period": "1"}


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


def test_hub_delay_holds_values_back_in_order() -> None:
    rec = Recorder()
    hub = OutputHub([rec], delay_s=0.3)
    hub.start()
    t0 = time.monotonic()
    hub.publish({"a": "1"})
    time.sleep(0.05)
    hub.publish({"a": "2"})
    time.sleep(0.1)
    assert rec.flush() and rec.got == []  # nothing yet: still within the delay
    deadline = time.monotonic() + 3
    while len(rec.got) < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
    assert rec.got == [{"a": "1"}, {"a": "2"}]  # both, in order (no change skipped)
    assert time.monotonic() - t0 >= 0.3
    # pause acts at once; resuming catches up with what the delay has let through
    hub.set_mode(OutputMode.PAUSED)
    hub.publish({"a": "3"})
    time.sleep(0.5)
    assert rec.flush() and rec.got[-1] == {"a": "2"}
    hub.set_mode(OutputMode.LIVE)
    assert rec.flush() and rec.got[-1] == {"a": "3"}
    hub.stop()


def test_hub_delay_slow_worker_does_not_hold_back_the_others() -> None:
    # e.g. vMix API timing out (1 s per try) next to the XML file: the file must stay current
    class Slow(Recorder):
        name = "slow"

        def write(self, values: dict[str, str]) -> None:
            time.sleep(1.0)

    fast, slow = Recorder(), Slow()
    hub = OutputHub([fast, slow], delay_s=0.2)
    hub.start()
    for i in range(30):  # 3 s at 10 Hz
        hub.publish({"n": str(i)})
        time.sleep(0.1)
    deadline = time.monotonic() + 2
    while fast.got[-1:] != [{"n": "29"}] and time.monotonic() < deadline:
        time.sleep(0.02)
    assert fast.got[-1] == {"n": "29"}
    assert len(hub._queue) == 0  # nothing piling up behind the slow worker
    hub.stop()
