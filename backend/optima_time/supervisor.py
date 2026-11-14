"""Watches the worker threads and restarts dead ones (SPEC 14.3).

An exception in the pipeline or an output must never take the process down: the pipeline thread
already catches per-frame errors; this catches what slips through (a thread that died). A thread
that is alive but whose heartbeat stopped is reported (Python threads can't be killed safely;
starting a second pipeline thread next to a stuck one would race it).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from optima_time import power

if TYPE_CHECKING:
    from optima_time.runner import Runner

log = logging.getLogger(__name__)

CHECK_EVERY_S = 1.0
STUCK_AFTER_S = 5.0


class Supervisor:
    def __init__(self, runner: Runner) -> None:
        self.runner = runner
        self.restarts = 0
        self.stuck = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="supervisor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        power.keep_awake(True)
        try:
            while not self._stop.wait(CHECK_EVERY_S):
                self.check()
        finally:
            power.keep_awake(False)

    def check(self) -> None:
        r = self.runner
        if not r.pipeline_alive():
            log.error("pipeline thread died; restarting it")
            self.restarts += 1
            r.state.log_event("thread_restarted", detail="pipeline")
            r.start_pipeline_thread()
        stuck = time.monotonic() - r.heartbeat > STUCK_AFTER_S
        if stuck and not self.stuck:
            log.error("pipeline heartbeat stopped for %.0f s", STUCK_AFTER_S)
            r.state.log_event("pipeline_stuck")
        self.stuck = stuck
        for w in r.hub.workers:
            if not w.alive():
                log.error("output %s died; restarting it", w.name)
                self.restarts += 1
                r.state.log_event("thread_restarted", detail=f"output {w.name}")
                w.start()
                r.state.publish_all()
