"""Alerts outside the app window (SPEC 13.2): the operator mostly watches vMix, not this app.

A problem that lasts longer than its delay raises one alert (Windows notification from the tray
icon, a system sound, a line in the event log); when it goes away, one "back to normal" message.
The monitor itself is pure (problems in, alerts out) so it is tested with a fake clock.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from optima_time.runner import Runner

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Condition:
    key: str
    delay_s: float  # how long the problem must last before it is announced
    title: str
    message: str
    recovered: str


CONDITIONS = [
    Condition(
        "source",
        3.0,
        "Zdroj obrazu vypadl",
        "Grafika drží poslední hodnoty. Zkontroluj NDI výstup ve vMixu, kabel nebo síť.",
        "Zdroj obrazu je zpět.",
    ),
    Condition(
        "output",
        3.0,
        "Zápis XML pro vMix selhává",
        "Grafika nedostává nové hodnoty. Soubor má asi otevřený jiný program.",
        "Zápis XML je zase v pořádku.",
    ),
    Condition(
        "stuck",
        0.0,
        "Zpracování se zaseklo",
        "Hodnoty se drží. Pokud to trvá, restartuj Optima Time.",
        "Zpracování zase běží.",
    ),
    Condition(
        "guard",
        60.0,
        "Tabule dlouho ukazuje něco jiného",
        "Už minutu nesedí kotvy (animace, reklama, posunutá kamera?). Hodnoty se drží.",
        "Tabule je zase vidět.",
    ),
]

Notify = Callable[[str, str, bool], None]  # title, message, is_problem


class AlertMonitor:
    def __init__(self, notify: Notify, clock: Callable[[], float] = time.monotonic) -> None:
        self.notify = notify
        self.clock = clock
        self._since: dict[str, float] = {}  # problem key -> when it started
        self._announced: set[str] = set()

    def check(self, problems: dict[str, bool]) -> None:
        now = self.clock()
        for c in CONDITIONS:
            if problems.get(c.key, False):
                start = self._since.setdefault(c.key, now)
                if c.key not in self._announced and now - start >= c.delay_s:
                    self._announced.add(c.key)
                    self.notify(c.title, c.message, True)
            else:
                self._since.pop(c.key, None)
                if c.key in self._announced:
                    self._announced.discard(c.key)
                    self.notify(c.recovered, "", False)


def current_problems(runner: Runner) -> dict[str, bool]:
    """Which conditions hold right now (pause and test mode are the operator's choice: no alert)."""
    source = runner.source_status().get("state")
    workers = runner.outputs_status()["workers"].values()
    result = runner.snapshot().result
    return {
        "source": source in ("lost", "none"),
        "output": any(w.get("ok") is False for w in workers),
        "stuck": runner.supervisor.stuck,
        "guard": result is not None and result.guard.state.value == "lost",
    }


class AlertThread:
    """Checks the runner twice a second and sends alerts to the event log and `sinks`."""

    def __init__(self, runner: Runner, sinks: list[Notify] | None = None) -> None:
        self.runner = runner
        self.sinks = list(sinks or [])
        self.monitor = AlertMonitor(self._notify)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="alerts", daemon=True)

    def _notify(self, title: str, message: str, problem: bool) -> None:
        log.warning("alert: %s %s", title, message) if problem else log.info("alert: %s", title)
        self.runner.state.log_event("alert" if problem else "alert_ok", text=title)
        for sink in self.sinks:
            try:
                sink(title, message, problem)
            except Exception:
                log.exception("alert sink failed")

    def _run(self) -> None:
        while not self._stop.wait(0.5):
            try:
                self.monitor.check(current_problems(self.runner))
            except Exception:
                log.exception("alert check failed")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


def system_sound(_title: str, _message: str, problem: bool) -> None:
    """A warning sound on Windows when a problem starts."""
    import sys

    if problem and sys.platform == "win32":
        import winsound

        winsound.MessageBeep(winsound.MB_ICONHAND)
