"""What kind of change a new reading is, and what it takes to accept it (SPEC 11.4).

The cost of errors is asymmetric (SPEC 1, priority 1): an expected change (the clock ticking
one step, a goal +1) is accepted fast; anything else must hold for a while first.

| field  | expected -> fast                          | unexpected -> slow                        |
|--------|-------------------------------------------|-------------------------------------------|
| clock  | step <= max_step in the counting direction | unexpected_reads reads over unexpected_ms |
| number | +1: increment_reads equal reads             | the value must hold unexpected_ms         |
| period | +1: increment_reads equal reads             | the value must hold unexpected_ms         |

"Appear" is a value after a blank (a penalty starting); "initial" is the very first value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from optima_time.fields.formats import ClockValue, NumberValue
from optima_time.fields.models import ClockField, Direction, NumberField, PeriodField

Value = ClockValue | NumberValue
AnyField = ClockField | NumberField | PeriodField


class ChangeKind(StrEnum):
    SAME = "same"
    EXPECTED = "expected"
    UNEXPECTED = "unexpected"
    APPEAR = "appear"  # a value after a blank
    INITIAL = "initial"  # nothing was ever published


@dataclass(frozen=True)
class Requirement:
    reads: int  # consistent reads needed
    ms: int  # time the candidate must hold (first to last read)


def clock_step(a: ClockValue, b: ClockValue, field: ClockField, direction: Direction) -> bool:
    """Is a -> b one normal tick: a small step in the counting direction?"""
    delta = b.tenths - a.tenths
    if delta == 0 or abs(delta) > field.max_step_ms // 100:
        return False
    if direction is Direction.DOWN:
        return delta < 0
    if direction is Direction.UP:
        return delta > 0
    return True  # AUTO before the direction is known: either way


def clock_caught_up(
    a: ClockValue, b: ClockValue, field: ClockField, direction: Direction, gap_ms: int
) -> bool:
    """After a gap without reads (layout guard, occlusion, unreadable frames) a running clock
    may have moved on by at most the time that passed, in its counting direction."""
    if direction is Direction.AUTO:
        return False  # without a known direction any jump could pass
    delta = b.tenths - a.tenths
    limit = (field.max_step_ms + gap_ms) // 100
    if direction is Direction.DOWN:
        return -limit <= delta < 0
    return 0 < delta <= limit


def continues(field: AnyField, a: Value, b: Value, direction: Direction) -> bool:
    """Does reading b continue a candidate whose latest value is a? A clock may tick on while
    it is being confirmed; a number must stay the same."""
    if a.key == b.key:
        return True
    if isinstance(field, ClockField) and isinstance(a, ClockValue) and isinstance(b, ClockValue):
        return clock_step(a, b, field, direction)
    return False


def classify(
    field: AnyField,
    published: Value | None,
    ever_published: bool,
    value: Value,
    confidence: float,
    direction: Direction,
    gap_ms: int = 0,
) -> tuple[ChangeKind, Requirement]:
    """gap_ms: time since the published value was last read (0 = just now)."""
    if published is not None and published.key == value.key:
        return ChangeKind.SAME, Requirement(1, 0)

    if isinstance(field, ClockField):
        slow = Requirement(field.unexpected_reads, field.unexpected_ms)
        if not ever_published:
            return ChangeKind.INITIAL, slow
        if published is None:
            return ChangeKind.APPEAR, Requirement(field.appear_reads, 0)
        assert isinstance(published, ClockValue) and isinstance(value, ClockValue)
        if clock_step(published, value, field, direction):
            reads = 1 if confidence >= field.fast_min_confidence else 2
            return ChangeKind.EXPECTED, Requirement(reads, 0)
        if gap_ms > 0 and clock_caught_up(published, value, field, direction, gap_ms):
            return ChangeKind.EXPECTED, Requirement(2, 0)  # caught up: one more read to be safe
        return ChangeKind.UNEXPECTED, slow

    # number and period
    assert isinstance(value, NumberValue)
    slow = Requirement(field.increment_reads, field.unexpected_ms)
    if not ever_published:
        return ChangeKind.INITIAL, Requirement(field.initial_reads, 0)
    if published is None:
        return ChangeKind.APPEAR, Requirement(field.initial_reads, 0)
    assert isinstance(published, NumberValue)
    if value.value == published.value + 1:
        return ChangeKind.EXPECTED, Requirement(field.increment_reads, 0)
    return ChangeKind.UNEXPECTED, slow
