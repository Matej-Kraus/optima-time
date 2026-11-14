"""Parsing and rendering of field values: clock, number, period.

Pure functions, no I/O. A reading (OCR text) is parsed into a typed value or rejected (None).
Parsing is strict: anything that doesn't fit the field's format is rejected, so an invalid
value never leaves the process (SPEC 16.2 "fail safe").

Separator repair (SPEC 11.2 step 3, M0 report): the OCR model sometimes drops the ':' / '.' or
confuses them. Two digits after the separator means mm:ss, one means ss.d. Without a
separator the candidates are tried and the one closest to the last valid value wins; with no
last value an ambiguous reading is rejected.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class ClockStyle(StrEnum):
    AS_IS = "as_is"  # exactly as on the board: "00:00", "02:00", "54.7"
    NO_LEADING_ZERO = "no_leading_zero"  # "0:00", "2:00", "54.7"
    LEADING_ZERO = "leading_zero"  # "00:00", "02:00", "54.7"


class NumberStyle(StrEnum):
    AS_IS = "as_is"
    STRIP_ZEROS = "strip_zeros"  # "03" -> "3"
    PAD_ZEROS = "pad_zeros"  # "3" -> "03" (to max_digits)


class Align(StrEnum):
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True)
class ClockSpec:
    tenths: bool = False  # the board switches to ss.d in the last minute
    max_minutes: int = 999
    style: ClockStyle = ClockStyle.AS_IS


@dataclass(frozen=True)
class NumberSpec:
    min_digits: int = 1
    max_digits: int = 2
    style: NumberStyle = NumberStyle.STRIP_ZEROS


@dataclass(frozen=True)
class PeriodSpec:
    min_value: int = 1
    max_value: int = 4
    names: tuple[tuple[int, str], ...] = ()  # optional mapping, e.g. ((1, "1. tretina"),)


@dataclass(frozen=True)
class ClockValue:
    tenths: int  # total time in tenths of a second
    board: str  # normalized text as the board shows it: "00:00", "1:32", "54.7"
    has_tenths: bool  # shown as ss.d

    @property
    def key(self) -> tuple[int, bool]:
        return (self.tenths, self.has_tenths)


@dataclass(frozen=True)
class NumberValue:
    value: int
    board: str  # digits as read, e.g. "03"

    @property
    def key(self) -> int:
        return self.value


Value = ClockValue | NumberValue

_KEEP_CLOCK = re.compile(r"[^0-9:.]")
_KEEP_DIGITS = re.compile(r"[^0-9]")


def clean(text: str, keep: re.Pattern[str]) -> str:
    """NFKC (full-width digits -> ASCII), then drop everything not allowed."""
    return keep.sub("", unicodedata.normalize("NFKC", text))


# --- clock ------------------------------------------------------------------------------


def _mmss(minutes: str, seconds: str, spec: ClockSpec) -> ClockValue | None:
    if not minutes or len(seconds) != 2:
        return None
    m, s = int(minutes), int(seconds)
    if s >= 60 or m > spec.max_minutes:
        return None
    return ClockValue((m * 60 + s) * 10, f"{minutes}:{seconds}", False)


def _ssd(seconds: str, tenth: str, spec: ClockSpec) -> ClockValue | None:
    if not spec.tenths or not 1 <= len(seconds) <= 2 or len(tenth) != 1:
        return None
    s = int(seconds)
    if s >= 60:
        return None
    return ClockValue(s * 10 + int(tenth), f"{seconds}.{tenth}", True)


def parse_clock(text: str, spec: ClockSpec, last: ClockValue | None = None) -> ClockValue | None:
    raw = clean(text, _KEEP_CLOCK)
    if not raw:
        return None
    seps = [i for i, c in enumerate(raw) if c in ":."]
    if len(seps) > 1:
        return None
    if seps:
        i = seps[0]
        before, after = raw[:i], raw[i + 1 :]
        if not before:
            return None
        if len(after) == 2:  # "12:45" or "12.45" (confused separator)
            return _mmss(before, after, spec)
        if len(after) == 1:  # "54.7" or "54:7"
            return _ssd(before, after, spec)
        return None
    # No separator: try every reading the format allows.
    candidates = [
        c
        for c in (
            _mmss(raw[:-2], raw[-2:], spec) if len(raw) >= 3 else None,
            _ssd(raw[:-1], raw[-1:], spec) if 2 <= len(raw) <= 3 else None,
        )
        if c is not None
    ]
    if len(candidates) == 1 and (last is None or not spec.tenths):
        return candidates[0]
    if not candidates or last is None:
        return None
    return min(candidates, key=lambda c: abs(c.tenths - last.tenths))


def render_clock(value: ClockValue, style: ClockStyle) -> str:
    if style is ClockStyle.AS_IS:
        return value.board
    if value.has_tenths:
        return f"{value.tenths // 10}.{value.tenths % 10}"
    m, s = divmod(value.tenths // 10, 60)
    if style is ClockStyle.LEADING_ZERO:
        return f"{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# --- number and period -------------------------------------------------------------------


def parse_number(text: str, spec: NumberSpec) -> NumberValue | None:
    raw = clean(text, _KEEP_DIGITS)
    if not spec.min_digits <= len(raw) <= spec.max_digits:
        return None
    return NumberValue(int(raw), raw)


def render_number(value: NumberValue, spec: NumberSpec) -> str:
    match spec.style:
        case NumberStyle.AS_IS:
            return value.board
        case NumberStyle.STRIP_ZEROS:
            return str(value.value)
        case NumberStyle.PAD_ZEROS:
            return f"{value.value:0{spec.max_digits}d}"


def parse_period(text: str, spec: PeriodSpec) -> NumberValue | None:
    raw = clean(text, _KEEP_DIGITS)
    if len(raw) != 1:
        return None
    value = int(raw)
    if not spec.min_value <= value <= spec.max_value:
        return None
    return NumberValue(value, raw)


def render_period(value: NumberValue, spec: PeriodSpec) -> str:
    return dict(spec.names).get(value.value, str(value.value))


# --- common ------------------------------------------------------------------------------


def align(text: str, mode: Align, width: int) -> str:
    """Pad with spaces to a fixed width so the graphic doesn't jump (SPEC 11.3)."""
    if mode is Align.LEFT:
        return text.ljust(width)
    if mode is Align.RIGHT:
        return text.rjust(width)
    return text
