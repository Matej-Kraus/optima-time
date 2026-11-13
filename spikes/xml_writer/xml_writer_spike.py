"""Spike B: rewrite a vMix XML data file 10x a second and serve the same XML over HTTP.

One-off experiment (Milestone 0), not product code. Matěj points a real vMix at the file
(and then at the URL) and watches for errors and blank flashes. Procedure:
docs/MANUAL_TESTS.md, test M0-B.

Writes are atomic: content goes to a temp file in the same folder, which then replaces the
target via os.replace(). The target is never held open. If the replace fails because a reader
(vMix, antivirus) has the file open (PermissionError on Windows), it is retried after a few ms;
only the newest state is ever written, so nothing piles up.

Fields (as in production + the new ones + a sequence number to spot stale reads):
  Time        counts down one second per write (so it visibly moves 10x a second)
  penaltyh1/2, penaltya1/2   run for 5 s, then blank for 5 s (tests blank handling)
  scoreh, scorea, period     change every 10 s / 15 s / 30 s
  seq         write number

Usage (Windows, in the repo):
  uv run python spikes/xml_writer/xml_writer_spike.py --path C:\\vmix-data\\optima_test.xml
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.sax.saxutils import escape

RETRY_SLEEP_S = 0.005
SLOW_WRITE_MS = 250.0


def build_xml(values: dict[str, str], newline: str) -> bytes:
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<root>"]
    for name in sorted(values):  # ordinal order: "Time" before "penaltya1", as today
        value = values[name]
        lines.append(f"  <{name}>{escape(value)}</{name}>" if value else f"  <{name}/>")
    lines.append("</root>")
    return (newline.join(lines) + newline).encode("utf-8")


def fmt_clock(total_s: int) -> str:
    return f"{total_s // 60}:{total_s % 60:02d}"


def state_at(seq: int, rate: float) -> dict[str, str]:
    t = seq / rate  # seconds since start
    period_s = 20 * 60
    clock = period_s - (seq % period_s)
    running = int(t) % 10 < 5
    penalty = fmt_clock(120 - int(t) % 120)
    return {
        "Time": fmt_clock(clock),
        "penaltyh1": penalty if running else "",
        "penaltyh2": penalty if running and int(t) % 20 < 10 else "",
        "penaltya1": "" if running else penalty,
        "penaltya2": "",
        "scoreh": str(int(t) // 10 % 20),
        "scorea": str(int(t) // 15 % 20),
        "period": str(int(t) // 30 % 4 + 1),
        "seq": str(seq),
    }


class Stats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.writes = 0
        self.retries = 0
        self.slow_writes = 0
        self.max_write_ms = 0.0
        self.write_ms: list[float] = []
        self.errors: list[str] = []
        self.http_requests = 0
        self.reader_checks = 0
        self.reader_failures: list[str] = []

    def snapshot(self) -> dict:
        with self.lock:
            ms = sorted(self.write_ms)
            return {
                "writes": self.writes,
                "retries_after_permission_error": self.retries,
                "writes_slower_than_250ms": self.slow_writes,
                "write_ms_median": round(ms[len(ms) // 2], 2) if ms else None,
                "write_ms_p99": round(ms[int(len(ms) * 0.99)], 2) if ms else None,
                "write_ms_max": round(self.max_write_ms, 2),
                "errors": self.errors[-10:],
                "http_requests": self.http_requests,
                "self_check_reads": self.reader_checks,
                "self_check_failures": self.reader_failures[-10:],
            }


def write_atomic(path: Path, data: bytes, stats: Stats, stop: threading.Event) -> None:
    t0 = time.monotonic_ns()
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        while True:
            try:
                os.replace(tmp, path)
                break
            except PermissionError as error:
                with stats.lock:
                    stats.retries += 1
                if stop.is_set():
                    raise
                if (time.monotonic_ns() - t0) / 1e6 > 5000:
                    raise TimeoutError(f"replace blocked for 5 s: {error}") from error
                time.sleep(RETRY_SLEEP_S)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    ms = (time.monotonic_ns() - t0) / 1e6
    with stats.lock:
        stats.writes += 1
        stats.write_ms.append(ms)
        stats.max_write_ms = max(stats.max_write_ms, ms)
        if ms > SLOW_WRITE_MS:
            stats.slow_writes += 1
            stats.errors.append(f"{time.strftime('%H:%M:%S')} slow write {ms:.0f} ms")


class Latest:
    """Latest XML/JSON, shared with the HTTP server."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.xml = b""
        self.values: dict[str, str] = {}


def make_handler(latest: Latest, stats: Stats) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            with latest.lock:
                xml, values = latest.xml, dict(latest.values)
            if self.path.split("?")[0] == "/data/values.xml":
                body, ctype = xml, "application/xml; charset=utf-8"
            elif self.path.split("?")[0] == "/data/values.json":
                body, ctype = json.dumps(values).encode(), "application/json; charset=utf-8"
            else:
                self.send_error(404)
                return
            with stats.lock:
                stats.http_requests += 1
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass  # keep the console for stats

    return Handler


def self_check_reader(path: Path, fields: set[str], stats: Stats, stop: threading.Event) -> None:
    """Reads like vMix (every 100 ms open/read/close) and checks the XML is whole and complete."""
    while not stop.wait(0.1):
        try:
            with path.open("rb") as f:
                data = f.read()
            root = ET.fromstring(data)
            missing = fields - {child.tag for child in root}
            problem = f"missing {sorted(missing)}" if missing else None
        except FileNotFoundError:
            problem = None  # between start and first write
        except (ET.ParseError, PermissionError, OSError) as error:
            problem = f"{type(error).__name__}: {error}"
        with stats.lock:
            stats.reader_checks += 1
            if problem:
                stats.reader_failures.append(f"{time.strftime('%H:%M:%S')} {problem}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--path", type=Path, default=Path(__file__).parent / "out" / "optima_test.xml"
    )
    parser.add_argument("--rate", type=float, default=10.0, help="writes per second")
    parser.add_argument("--minutes", type=float, default=10.0)
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--newline", choices=["lf", "crlf"], default="crlf")
    parser.add_argument("--no-self-check", action="store_true")
    args = parser.parse_args()

    path: Path = args.path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    newline = "\r\n" if args.newline == "crlf" else "\n"
    stats, latest, stop = Stats(), Latest(), threading.Event()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(latest, stats))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if not args.no_self_check:
        fields = set(state_at(0, args.rate))
        threading.Thread(
            target=self_check_reader, args=(path, fields, stats, stop), daemon=True
        ).start()

    print(f"file: {path}")
    print(f"http: http://127.0.0.1:{args.port}/data/values.xml  (and /data/values.json)")
    print(f"{args.rate:g} writes/s for {args.minutes:g} min. Ctrl+C stops early.\n")

    period_ns = int(1e9 / args.rate)
    start = time.monotonic_ns()
    end = start + int(args.minutes * 60e9)
    seq, next_report = 0, start + int(10e9)
    try:
        while (now := time.monotonic_ns()) < end:
            values = state_at(seq, args.rate)
            xml = build_xml(values, newline)
            with latest.lock:
                latest.xml, latest.values = xml, values
            try:
                write_atomic(path, xml, stats, stop)
            except Exception as error:  # report and keep going: this is what we measure
                with stats.lock:
                    stats.errors.append(
                        f"{time.strftime('%H:%M:%S')} {type(error).__name__}: {error}"
                    )
            seq += 1
            if now >= next_report:
                s = stats.snapshot()
                print(
                    f"{(now - start) / 60e9:5.1f} min  writes {s['writes']}"
                    f"  retries {s['retries_after_permission_error']}"
                    f"  max {s['write_ms_max']} ms  slow {s['writes_slower_than_250ms']}"
                    f"  http {s['http_requests']}  check-fail {len(s['self_check_failures'])}"
                )
                next_report += int(10e9)
            sleep_ns = start + seq * period_ns - time.monotonic_ns()
            if sleep_ns > 0:
                time.sleep(sleep_ns / 1e9)
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        stop.set()
        server.shutdown()

    summary = stats.snapshot() | {
        "minutes": round((time.monotonic_ns() - start) / 60e9, 2),
        "path": str(path),
    }
    report = path.with_name(path.stem + "_report.json")
    report.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("\n" + json.dumps(summary, indent=1))
    print(f"\nreport: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
