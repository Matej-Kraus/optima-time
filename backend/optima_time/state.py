"""Board state: published values, field states and the event log (SPEC 11.2, 13.2, 14.3).

Takes each frame's readings (or the news that there were none: source lost, layout guard
failed), runs every field's logic, and hands changed values to the output hub. Every event
(change, rejected candidate, blank, hold, guard and source changes) goes to an in-memory ring for
the UI and, when a log folder is set, to a daily JSONL file with wall-clock and monotonic time.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from optima_time.config.models import Profile
from optima_time.fields.confirm import Event, FieldLogic, FieldStatus
from optima_time.fields.template import Template
from optima_time.guard import GuardResult, GuardState
from optima_time.outputs.base import OutputHub
from optima_time.pipeline import FrameResult

log = logging.getLogger(__name__)


@dataclass
class LoggedEvent:
    wall: str  # ISO time with milliseconds and UTC offset
    mono_ns: int
    kind: str
    field: str = ""
    text: str = ""
    detail: str = ""


def derive(templates: dict[str, Template], values: dict[str, str]) -> dict[str, str]:
    """Derived fields from field values; a template that fails yields "" (never stale text)."""
    out = {}
    for did, t in templates.items():
        try:
            out[did] = t.render(values)
        except Exception:  # a bad filter argument slipped through: empty, not a crash
            out[did] = ""
    return out


def group(field_id: str) -> str:
    """Fields that differ only in a trailing number form a group (penaltyh1, penaltyh2)."""
    return re.sub(r"\d+$", "", field_id)


class BoardState:
    def __init__(
        self,
        profile: Profile,
        hub: OutputHub | None = None,
        log_dir: Path | None = None,
        initial: dict[str, str] | None = None,
        log_name: str = "events",
    ) -> None:
        self._lock = threading.RLock()
        self.hub = hub or OutputHub()
        self.log_dir = log_dir
        self.log_name = log_name  # events-<date>.jsonl; another instance uses events-<port>-…
        self.events: deque[LoggedEvent] = deque(maxlen=300)
        self.logic: dict[str, FieldLogic] = {}
        self.guard_state = GuardState.OFF
        self.source_ok = True
        self._apply(profile)
        if initial:  # start from the file's last values: no blank flash after a restart
            for fid, text in initial.items():
                if fid in self.logic:
                    self.logic[fid].text = text
        self._publish(None)

    # --- configuration

    def reconfigure(self, profile: Profile) -> None:
        with self._lock:
            self._apply(profile)
            self._publish(None)

    def _apply(self, profile: Profile) -> None:
        with self._lock:
            self.derived = {d.id: Template(d.template) for d in profile.derived if d.enabled}
            enabled = {f.id: f for f in profile.fields if f.enabled}
            for fid in list(self.logic):
                if fid not in enabled:
                    del self.logic[fid]
            for fid, f in enabled.items():
                if fid in self.logic:
                    self.logic[fid].reconfigure(f)
                else:
                    self.logic[fid] = FieldLogic(f)

    # --- values

    def values(self) -> dict[str, str]:
        with self._lock:
            return {fid: lg.text for fid, lg in self.logic.items()}

    def output_values(self) -> dict[str, str]:
        """What goes out: the fields plus the derived fields computed from them."""
        with self._lock:
            values = {fid: lg.text for fid, lg in self.logic.items()}
            return values | derive(self.derived, values)

    def fields(self) -> dict[str, dict]:
        with self._lock:
            return {
                fid: {
                    "text": lg.text,
                    "status": lg.status.value,
                    "held": lg.held_text is not None,
                    "pending": lg.candidate.latest.board if lg.candidate else None,
                }
                for fid, lg in self.logic.items()
            }

    def unsettled(self) -> set[str]:
        """Fields that need fresh reads even if their crop looks unchanged: a change waiting for
        confirmation, nothing confirmed yet, or the last read was unusable."""
        with self._lock:
            return {
                fid
                for fid, lg in self.logic.items()
                if lg.held_text is None
                and (
                    lg.candidate is not None
                    or (not lg.ever_published and lg.status is not FieldStatus.BLANK)
                    or lg.status in (FieldStatus.REJECTED, FieldStatus.STALE)
                )
            }

    def update(
        self,
        result: FrameResult | None,
        guard: GuardResult | None,
        source_ok: bool,
        now_ns: int | None = None,
    ) -> bool:
        """One frame's outcome. Returns True if a published value changed.

        now_ns is the frame's time for the confirmation rules: its arrival time live, its media
        time in tools/eval (which runs faster than real time)."""
        now = time.monotonic_ns() if now_ns is None else now_ns
        events: list[Event] = []
        with self._lock:
            self._source(source_ok)
            if guard is not None:
                self._guard(guard)
            readable = source_ok and result is not None and (guard is None or guard.ok)
            before = {fid: lg.published for fid, lg in self.logic.items()}
            for fid, lg in self.logic.items():
                read = result.fields.get(fid) if (readable and result) else None
                if read is None:
                    lg.stale()
                else:
                    peers = [
                        v
                        for other, v in before.items()
                        if other != fid and v is not None and group(other) == group(fid)
                    ]
                    events += lg.update(read, now, peers)
            changed = any(e.kind == "changed" for e in events)
            for e in events:
                self._log(e.kind, e.field_id, e.text, e.detail)
            if changed:
                self._publish(result.arrived_ns if result else None)
            return changed

    def publish_all(self) -> None:
        """Write the whole state (at start and when the source comes back, SPEC 12.1)."""
        with self._lock:
            self._publish(None)

    # --- operator actions

    def hold(self, field_id: str, text: str) -> None:
        with self._lock:
            for e in self.logic[field_id].hold(text):
                self._log(e.kind, e.field_id, e.text, e.detail)
            self._publish(None)

    def release(self, field_id: str) -> None:
        with self._lock:
            for e in self.logic[field_id].release():
                self._log(e.kind, e.field_id, e.text, e.detail)

    def clear_values(self) -> None:
        """Empty every value that isn't held (the operator's "Vyprázdnit hodnoty")."""
        with self._lock:
            for lg in self.logic.values():
                if lg.held_text is None:
                    lg.published, lg.text, lg.ever_published, lg.candidate = None, "", False, None
            self._log("cleared")
            self._publish(None)

    def log_event(self, kind: str, field: str = "", text: str = "", detail: str = "") -> None:
        with self._lock:
            self._log(kind, field, text, detail)

    # --- internals

    def _publish(self, arrived_ns: int | None) -> None:
        self.hub.publish(self.output_values(), arrived_ns)

    def _guard(self, guard: GuardResult) -> None:
        if guard.state is not self.guard_state:
            if guard.state is GuardState.LOST:
                self._log("guard_lost", detail=f"scores {guard.scores}")
            elif guard.state is GuardState.OK and self.guard_state is not GuardState.OFF:
                self._log("guard_ok", detail=f"scores {guard.scores}")
            self.guard_state = guard.state

    def _source(self, ok: bool) -> None:
        if ok != self.source_ok:
            self._log("source_ok" if ok else "source_lost")
            self.source_ok = ok
            if ok:
                self._publish(None)

    def _log(self, kind: str, field: str = "", text: str = "", detail: str = "") -> None:
        e = LoggedEvent(
            datetime.now().astimezone().isoformat(timespec="milliseconds"),
            time.monotonic_ns(),
            kind,
            field,
            text,
            detail,
        )
        self.events.append(e)
        if self.log_dir is None:
            return
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            path = self.log_dir / f"{self.log_name}-{time.strftime('%Y-%m-%d')}.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(e), ensure_ascii=False) + "\n")
        except OSError as error:  # the log must never stop the values
            log.warning("can't write event log: %s", error)


__all__ = ["BoardState", "FieldStatus", "LoggedEvent"]
