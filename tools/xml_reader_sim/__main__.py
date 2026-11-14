"""A reader that behaves like vMix's XML Data Source (SPEC 15.4).

Every --interval ms it opens the file, reads it, keeps it open for --hold ms (a slow reader makes
collisions more likely), closes it, and checks: the XML is whole and valid, the root is <root>,
and no field is missing. On Windows an open file can't be replaced (Python opens without
FILE_SHARE_DELETE), so the writer really collides with this reader. Elsewhere --emulate-lock
makes the in-process writer fail the same way while the reader holds the file.

Usage:
  # against a running app (or spikes/xml_writer), on the production PC:
  uv run python -m tools.xml_reader_sim --path C:\\vmix-data\\tabule.xml --minutes 10
  # self-contained: our XmlFileWorker writing 10 changes/s, reader colliding with it:
  uv run python -m tools.xml_reader_sim --with-writer --minutes 3 --emulate-lock
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import random
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from optima_time.outputs.xml import parse_xml
from optima_time.outputs.xml_file import XmlFileWorker

FIELDS = ["Time", "period", "scoreh", "scorea", "penaltyh1", "penaltyh2", "penaltya1", "penaltya2"]


@dataclass
class ReaderStats:
    reads: int = 0
    failures: int = 0  # invalid XML, wrong root, missing fields
    read_errors: int = 0  # couldn't open (e.g. mid-replace on some filesystems)
    examples: list[str] = field(default_factory=list)


class FileLock:
    """Emulates Windows: while the reader holds the file, replacing it fails."""

    def __init__(self) -> None:
        self.held = threading.Lock()

    def replace(self, src: str, dst: str) -> None:
        if not self.held.acquire(blocking=False):
            raise PermissionError(13, "The process cannot access the file (emulated)")
        try:
            os.replace(src, dst)
        finally:
            self.held.release()


def read_loop(
    path: Path,
    expected: set[str] | None,
    interval_s: float,
    hold_s: float,
    stop: threading.Event,
    stats: ReaderStats,
    lock: FileLock | None,
) -> None:
    while not stop.wait(interval_s):
        try:
            if lock:
                lock.held.acquire()
            try:
                with path.open("rb") as f:
                    data = f.read()
                    if hold_s:
                        time.sleep(hold_s)
            finally:
                if lock:
                    lock.held.release()
        except FileNotFoundError:
            continue  # not written yet
        except OSError as error:
            stats.read_errors += 1
            if len(stats.examples) < 10:
                stats.examples.append(f"read: {error}")
            continue
        stats.reads += 1
        try:
            values = parse_xml(data)
            if expected is None:
                expected = set(values)
            missing = expected - set(values)
            if missing:
                raise ValueError(f"missing fields {sorted(missing)}")
        except Exception as error:
            stats.failures += 1
            if len(stats.examples) < 10:
                stats.examples.append(f"{type(error).__name__}: {error}")


def writer_loop(worker: XmlFileWorker, rate: float, stop: threading.Event, sent: list) -> None:
    rng = random.Random(1)
    n = 0
    while not stop.wait(1 / rate):
        n += 1
        values = {f: "" if rng.random() < 0.1 else str(rng.randint(0, 99)) for f in FIELDS}
        values["Time"] = f"{n // 60 % 100}:{n % 60:02d}"
        worker.submit(values)
        sent[:] = [values]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--path", type=Path)
    parser.add_argument("--minutes", type=float, default=1.0)
    parser.add_argument("--interval", type=float, default=100, help="ms between reads")
    parser.add_argument("--hold", type=float, default=20, help="ms the file stays open")
    parser.add_argument("--with-writer", action="store_true", help="run our writer in-process")
    parser.add_argument("--rate", type=float, default=10, help="writer changes per second")
    parser.add_argument(
        "--emulate-lock",
        action="store_true",
        help="emulate Windows locking for the in-process writer",
    )
    args = parser.parse_args()

    path = args.path or Path(tempfile.mkdtemp(prefix="xml_reader_sim_")) / "tabule.xml"
    lock = FileLock() if args.emulate_lock and args.with_writer else None
    stop = threading.Event()
    stats = ReaderStats()
    worker = None
    sent: list = []
    if args.with_writer:
        worker = XmlFileWorker(path, replace=lock.replace if lock else os.replace)
        worker.start()
        worker.submit(dict.fromkeys(FIELDS, ""))
        worker.flush()
        threading.Thread(
            target=writer_loop, args=(worker, args.rate, stop, sent), daemon=True
        ).start()
    reader = threading.Thread(
        target=read_loop,
        args=(
            path,
            set(FIELDS) if args.with_writer else None,
            args.interval / 1000,
            args.hold / 1000,
            stop,
            stats,
            lock,
        ),
        daemon=True,
    )
    reader.start()
    print(f"reading {path} every {args.interval:g} ms for {args.minutes:g} min ...")
    with contextlib.suppress(KeyboardInterrupt):
        stop.wait(args.minutes * 60)
    stop.set()
    reader.join(2)
    report: dict = {"machine": platform.system(), "path": str(path), "reader": asdict(stats)}
    ok = stats.failures == 0
    if worker is not None:
        worker.flush(10)
        last_ok = bool(sent) and parse_xml(path.read_bytes()) == sent[0]
        worker.stop()
        report["writer"] = worker.status.as_dict() | {"final_file_is_last_values": last_ok}
        ok = ok and last_ok and worker.status.ok is True
    report["result"] = "OK" if ok else "FAILED"
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
