"""From single readings to the published value of one field (SPEC 11.2 steps 5-7, 11.4-11.6).

FieldLogic keeps the published value and at most one candidate. A VALID reading that differs
from the published value starts (or continues) a candidate; the candidate is published once it
meets its Requirement (plausibility.py). Anything doubtful keeps the last valid value.

Blank policy (SPEC 11.5): BLANK readings for blank_delay_ms in a row publish "" (clear), the
configured text (value), or nothing (hold). Manual hold (11.6) publishes the operator's text and
ignores OCR until released.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from optima_time.fields.formats import ClockValue
from optima_time.fields.models import BlankPolicy, Direction
from optima_time.fields.plausibility import (
    AnyField,
    ChangeKind,
    Requirement,
    Value,
    classify,
    continues,
)
from optima_time.pipeline import FieldRead, ReadStatus

CANDIDATE_TIMEOUT_MS = 1500  # a candidate without a consistent read for this long is dropped


class FieldStatus(StrEnum):
    NEW = "new"  # a new value was published now
    SAME = "same"  # read the published value
    PENDING = "pending"  # a change is waiting for confirmation
    REJECTED = "rejected"  # unreadable, invalid or low confidence
    BLANK = "blank"
    STALE = "stale"  # not read: source lost or the board shows something else
    HELD = "held"  # manual override


@dataclass
class Candidate:
    first: Value
    latest: Value
    kind: ChangeKind
    requirement: Requirement
    first_ns: int
    last_ns: int
    reads: int = 1

    def met(self) -> bool:
        return (
            self.reads >= self.requirement.reads
            and (self.last_ns - self.first_ns) / 1e6 >= self.requirement.ms
        )


@dataclass
class Event:
    kind: str  # "changed" | "rejected" | "blank" | "held" | "released"
    field_id: str
    text: str = ""
    detail: str = ""


class FieldLogic:
    def __init__(self, field: AnyField) -> None:
        self.field = field
        self.published: Value | None = None
        self.text: str = ""  # published text ("" = empty element)
        self.ever_published = False
        self.status = FieldStatus.STALE
        self.candidate: Candidate | None = None
        self.held_text: str | None = None
        self.direction: Direction = getattr(field, "direction", Direction.AUTO)
        self._learned_steps: list[int] = []  # signs of accepted clock ticks (direction auto)
        self._blank_since_ns: int | None = None
        self._seen_ns: int | None = None  # last time the published value was read or set

    # --- configuration

    def reconfigure(self, field: AnyField) -> None:
        """Apply edited settings; a changed format or type starts over."""
        if type(field) is not type(self.field) or field.spec() != self.field.spec():
            self.__init__(field)
            return
        self.field = field
        if getattr(field, "direction", Direction.AUTO) is not Direction.AUTO:
            self.direction = field.direction  # type: ignore[union-attr]

    # --- manual hold (SPEC 11.6)

    def hold(self, text: str) -> list[Event]:
        self.held_text = text
        self.candidate = None
        self.status = FieldStatus.HELD
        self.text = text
        return [Event("held", self.field.id, text)]

    def release(self) -> list[Event]:
        if self.held_text is None:
            return []
        self.held_text = None
        # the held text stays published until OCR confirms something (as at startup)
        self.published = None
        self.ever_published = False
        self.status = FieldStatus.STALE
        return [Event("released", self.field.id, self.text)]

    # --- per frame

    def stale(self) -> None:
        """Not read this frame (source lost, layout guard failed)."""
        if self.held_text is not None:
            self.status = FieldStatus.HELD
            return
        self.candidate = None
        self._blank_since_ns = None
        self.status = FieldStatus.STALE

    def update(self, read: FieldRead, now_ns: int, peers: Sequence[Value] = ()) -> list[Event]:
        """peers: published values of sibling fields (see plausibility.classify)."""
        if self.held_text is not None:
            self.status = FieldStatus.HELD
            return []
        events: list[Event] = []
        self._expire_candidate(now_ns, events)

        if read.status is ReadStatus.BLANK:
            self.status = FieldStatus.BLANK
            return events + self._blank(now_ns)
        self._blank_since_ns = None
        if read.status is not ReadStatus.VALID or read.value is None:
            self.status = FieldStatus.REJECTED
            return events

        value = read.value
        conf = read.reading.confidence if read.reading else 0.0
        c = self.candidate
        if c is not None and continues(self.field, c.latest, value, self.direction):
            c.latest, c.last_ns, c.reads = value, now_ns, c.reads + 1
        else:
            gap_ms = 0 if self._seen_ns is None else (now_ns - self._seen_ns) // 1_000_000
            kind, req = classify(
                self.field,
                self.published,
                self.ever_published,
                value,
                conf,
                self.direction,
                gap_ms,
                peers,
            )
            if kind is ChangeKind.SAME:
                self._seen_ns = now_ns
                if c is not None:
                    events.append(self._rejected(c, "the published value came back"))
                self.candidate = None
                self.status = FieldStatus.SAME
                return events
            if c is not None:
                events.append(self._rejected(c, f"replaced by {value.board}"))
            c = self.candidate = Candidate(value, value, kind, req, now_ns, now_ns)

        if c.met():
            self.candidate = None
            self._seen_ns = now_ns
            self._learn_direction(c)
            events += self._publish(c.latest, f"{c.kind.value}, {c.reads} reads")
            self.status = FieldStatus.NEW
        else:
            self.status = FieldStatus.PENDING
        return events

    # --- internals

    def _publish(self, value: Value | None, detail: str, text: str | None = None) -> list[Event]:
        new_text = text if text is not None else (self.field.render(value) if value else "")
        self.published = value
        self.ever_published = self.ever_published or value is not None
        if new_text == self.text:
            return []
        self.text = new_text
        return [Event("changed", self.field.id, new_text, detail)]

    def _blank(self, now_ns: int) -> list[Event]:
        if self._blank_since_ns is None:
            self._blank_since_ns = now_ns
        if (now_ns - self._blank_since_ns) / 1e6 < self.field.blank_delay_ms:
            return []
        match self.field.blank:
            case BlankPolicy.HOLD:
                return []
            case BlankPolicy.CLEAR:
                if self.published is None and self.text == "":
                    return []
                self.candidate = None
                return self._publish(None, "blank")
            case BlankPolicy.VALUE:
                self.candidate = None
                return self._publish(None, "blank", text=self.field.blank_value)

    def _expire_candidate(self, now_ns: int, events: list[Event]) -> None:
        c = self.candidate
        if c is None:
            return
        limit = max(CANDIDATE_TIMEOUT_MS, c.requirement.ms + 500)
        if (now_ns - c.last_ns) / 1e6 > limit:
            events.append(self._rejected(c, "no confirming read"))
            self.candidate = None

    def _rejected(self, c: Candidate, why: str) -> Event:
        return Event("rejected", self.field.id, c.latest.board, f"{c.kind.value}: {why}")

    def _learn_direction(self, c: Candidate) -> None:
        """Counting direction from accepted ticks: two in the same direction decide it."""
        if self.direction is not Direction.AUTO or c.kind is not ChangeKind.EXPECTED:
            return
        if not (isinstance(c.first, ClockValue) and isinstance(self.published, ClockValue)):
            return
        sign = 1 if c.first.tenths > self.published.tenths else -1
        self._learned_steps = [*self._learned_steps[-1:], sign]
        if len(self._learned_steps) == 2 and self._learned_steps[0] == self._learned_steps[1]:
            self.direction = Direction.UP if sign > 0 else Direction.DOWN
