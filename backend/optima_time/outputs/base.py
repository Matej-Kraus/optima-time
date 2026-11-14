"""Output workers and the hub that feeds them (SPEC 7.2, 12.1).

Each output runs in its own thread and holds only the latest values ("latest wins"), so a slow
target never blocks the pipeline and nothing piles up. The hub decides what reaches the
outputs: live values, nothing (paused: the graphic freezes), or test data.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import StrEnum

log = logging.getLogger(__name__)

RETRY_AFTER_ERROR_S = 0.05


@dataclass
class OutputStatus:
    ok: bool | None = None  # None: nothing written yet
    message: str = ""
    writes: int = 0
    failures: int = 0
    slow_writes: int = 0
    last_ok_wall: float | None = None  # time.time() of the last successful write
    last_write_ms: float | None = None
    max_write_ms: float = 0.0
    last_latency_ms: float | None = None  # frame arrival -> write done
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=2000), repr=False)

    def as_dict(self) -> dict:
        d = asdict(self)
        lat = sorted(d.pop("latencies_ms"))
        d["latency_ms_p50"] = round(lat[len(lat) // 2], 1) if lat else None
        d["latency_ms_p95"] = round(lat[int(0.95 * (len(lat) - 1))], 1) if lat else None
        return d


class OutputWorker(ABC):
    name = "output"

    def __init__(self) -> None:
        self.status = OutputStatus()
        self._cond = threading.Condition()
        self._pending: tuple[dict[str, str], int | None] | None = None
        self._stop = False
        self._busy = False
        self._thread: threading.Thread | None = None

    @abstractmethod
    def write(self, values: dict[str, str]) -> None:
        """Deliver the values; raise on failure (the worker retries with the newest values)."""

    def has_newer(self) -> bool:
        with self._cond:
            return self._pending is not None

    def take_pending(self) -> dict[str, str] | None:
        """Take newer values submitted while a write is in progress (the write then goes on with
        them instead of the old ones)."""
        with self._cond:
            if self._pending is None:
                return None
            values, _ = self._pending
            self._pending = None
            return values

    def submit(self, values: dict[str, str], arrived_ns: int | None = None) -> None:
        with self._cond:
            self._pending = (dict(values), arrived_ns)
            self._cond.notify()

    def start(self) -> None:
        self._stop = False
        self._thread = threading.Thread(target=self._run, name=f"output-{self.name}", daemon=True)
        self._thread.start()

    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self, final: dict[str, str] | None = None, timeout: float = 3.0) -> None:
        """Stop the thread; write `final` first if given (e.g. emptied values on exit)."""
        if final is not None:
            self.submit(final)
            self.flush(timeout)
        with self._cond:
            self._stop = True
            self._cond.notify()
        if self._thread is not None:
            self._thread.join(timeout)

    def flush(self, timeout: float = 3.0) -> bool:
        """Wait until the pending values are written (for tests and shutdown)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._cond:
                if self._pending is None and not self._busy:
                    return True
            time.sleep(0.005)
        return False

    def _run(self) -> None:
        while True:
            with self._cond:
                while self._pending is None and not self._stop:
                    self._cond.wait()
                if self._stop and self._pending is None:
                    return
                assert self._pending is not None
                values, arrived_ns = self._pending
                self._pending = None
                self._busy = True
            t0 = time.monotonic_ns()
            try:
                self.write(values)
            except Exception as error:  # report, then retry with the newest values
                self.status.ok = False
                self.status.failures += 1
                self.status.message = f"{type(error).__name__}: {error}"
                log.warning("%s: write failed: %s", self.name, self.status.message)
                with self._cond:
                    if self._pending is None:
                        self._pending = (values, arrived_ns)
                    self._busy = False
                time.sleep(RETRY_AFTER_ERROR_S)
                continue
            done = time.monotonic_ns()
            s = self.status
            s.ok, s.writes, s.last_ok_wall = True, s.writes + 1, time.time()
            s.last_write_ms = (done - t0) / 1e6
            s.max_write_ms = max(s.max_write_ms, s.last_write_ms)
            if not s.message.startswith("slow"):
                s.message = ""
            if arrived_ns is not None:
                s.last_latency_ms = (done - arrived_ns) / 1e6
                s.latencies_ms.append(s.last_latency_ms)
            with self._cond:
                self._busy = False


class OutputMode(StrEnum):
    LIVE = "live"
    PAUSED = "paused"  # nothing is written: the graphic keeps the last values
    TEST = "test"  # test data is shown; live values wait


class OutputHub:
    """Routes values to the workers according to the mode."""

    def __init__(self, workers: list[OutputWorker] | None = None) -> None:
        self.workers = workers or []
        self.mode = OutputMode.LIVE
        self._live: dict[str, str] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        for w in self.workers:
            w.start()

    def stop(self, final: dict[str, str] | None = None) -> None:
        for w in self.workers:
            w.stop(final)

    def publish(self, values: dict[str, str], arrived_ns: int | None = None) -> None:
        with self._lock:
            self._live = dict(values)
            if self.mode is not OutputMode.LIVE:
                return
        for w in self.workers:
            w.submit(values, arrived_ns)

    def set_mode(self, mode: OutputMode) -> None:
        with self._lock:
            self.mode = mode
            live = dict(self._live)
        if mode is OutputMode.LIVE:  # catch up at once
            for w in self.workers:
                w.submit(live)

    def write_test(self, values: dict[str, str]) -> None:
        with self._lock:
            self.mode = OutputMode.TEST
        for w in self.workers:
            w.submit(values)
