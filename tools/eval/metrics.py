"""Evaluation metrics against ground truth (SPEC 15.3). Pure functions over per-frame results.

Ground truth (truth.jsonl): one line per change of a field's board text or visibility:
  {"frame": 120, "t": 4.8, "field": "Time", "value": "01:10", "visible": true}

Naive publishing (the Milestone 1 baseline, no confirmation yet): a field publishes its latest
VALID reading and holds it; a "clear" field publishes "" after blank_delay_ms of blank reads.

A published value is wrong when it is neither the current truth nor, within STALE_WINDOW_S of a
change, the previous truth value (publishing late is not wrong, publishing nonsense is). While a
field can't be seen (goal animation, someone in front) the right thing is to hold the last value
seen, so the last visible value is right then (and so is the board's real value).
"""

from __future__ import annotations

import bisect
import json
import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from optima_time.fields.models import BlankPolicy, ClockField, NumberField, PeriodField
from optima_time.pipeline import ReadStatus

AnyField = ClockField | NumberField | PeriodField
STALE_WINDOW_S = 1.0


@dataclass
class TruthTrack:
    """A field's truth over frames: change points with their value and visibility."""

    frames: list[int] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    visible: list[bool] = field(default_factory=list)

    def at(self, frame: int) -> tuple[str, bool]:
        i = bisect.bisect_right(self.frames, frame) - 1
        if i < 0:
            return "", False
        return self.values[i], self.visible[i]


def load_truth(path: Path) -> dict[str, TruthTrack]:
    tracks: dict[str, TruthTrack] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        t = tracks.setdefault(e["field"], TruthTrack())
        t.frames.append(int(e["frame"]))
        t.values.append(str(e["value"]))
        t.visible.append(bool(e.get("visible", True)))
    return tracks


@dataclass
class Observation:
    """What the pipeline produced for one field in one frame."""

    frame: int
    status: ReadStatus
    text: str  # raw OCR text ("" when skipped)
    confidence: float
    key: object | None  # comparable value key when VALID


def key_of(f: AnyField, text: str) -> object | None:
    """Comparable key of a board text (None for "" / unparsable)."""
    if not text:
        return None
    value = f.parse(text, None)
    return None if value is None else value.key


@dataclass
class FieldMetrics:
    field_id: str
    lit: int = 0  # visible crops with a value on the board
    lit_correct: int = 0
    lit_wrong_value: int = 0  # VALID but a different value
    lit_invalid: int = 0
    lit_low_conf: int = 0
    lit_blank: int = 0
    unlit: int = 0  # visible crops with the field dark
    unlit_read_as_value: int = 0
    changes: int = 0
    captured: int = 0
    delays_ms: list[float] = field(default_factory=list)
    wrong_published: int = 0  # times a wrong value was published
    wrong_published_frames: int = 0
    examples: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        def pct(a: int, b: int) -> float | None:
            return round(100 * a / b, 2) if b else None

        d = sorted(self.delays_ms)
        return {
            "field": self.field_id,
            "crop_accuracy_%": pct(self.lit_correct, self.lit),
            "lit_crops": self.lit,
            "wrong_value": self.lit_wrong_value,
            "invalid": self.lit_invalid,
            "low_conf": self.lit_low_conf,
            "blank": self.lit_blank,
            "unlit_crops": self.unlit,
            "unlit_read_as_value": self.unlit_read_as_value,
            "changes": self.changes,
            "captured_%": pct(self.captured, self.changes),
            "delay_ms_median": round(statistics.median(d), 1) if d else None,
            "delay_ms_p95": round(d[int(0.95 * (len(d) - 1))], 1) if d else None,
            "wrong_published": self.wrong_published,
            "wrong_published_frames": self.wrong_published_frames,
        }


def evaluate_field(
    f: AnyField,
    truth: TruthTrack,
    observations: Iterable[Observation],
    fps: float,
    max_examples: int = 20,
) -> FieldMetrics:
    m = FieldMetrics(f.id)
    obs = list(observations)
    published: object | None = None  # naive publishing state (key)
    blank_since: int | None = None
    blank_frames = max(1, round(f.blank_delay_ms / 1000 * fps))
    stale_frames = round(STALE_WINDOW_S * fps)
    last_visible: tuple[object | None, int] | None = None  # (key, since frame)
    prev_visible_key: object | None = None
    published_trace: list[object | None] = []
    wrong_now = False

    for o in obs:
        text, visible = truth.at(o.frame)
        tkey = key_of(f, text)
        # 1) engine accuracy on visible crops
        if visible:
            if text:
                m.lit += 1
                if o.status is ReadStatus.VALID and o.key == tkey:
                    m.lit_correct += 1
                else:
                    match o.status:
                        case ReadStatus.VALID:
                            m.lit_wrong_value += 1
                        case ReadStatus.INVALID:
                            m.lit_invalid += 1
                        case ReadStatus.LOW_CONFIDENCE:
                            m.lit_low_conf += 1
                        case ReadStatus.BLANK:
                            m.lit_blank += 1
                    if len(m.examples) < max_examples:
                        m.examples.append(
                            {
                                "frame": o.frame,
                                "truth": text,
                                "status": o.status.value,
                                "read": o.text,
                                "conf": round(o.confidence, 3),
                            }
                        )
            else:
                m.unlit += 1
                if o.status is ReadStatus.VALID:
                    m.unlit_read_as_value += 1
            if last_visible is None or last_visible[0] != tkey:
                prev_visible_key = last_visible[0] if last_visible else None
                last_visible = (tkey, o.frame)
        # 2) naive publishing
        if o.status is ReadStatus.VALID:
            published, blank_since = o.key, None
        elif o.status is ReadStatus.BLANK:
            blank_since = o.frame if blank_since is None else blank_since
            if f.blank is BlankPolicy.CLEAR and o.frame - blank_since + 1 >= blank_frames:
                published = None
        else:
            blank_since = None
        published_trace.append(published)
        # expected: last visible truth, or the one before it shortly after a change
        cur, since = last_visible if last_visible else (None, o.frame)
        ok = (
            published == cur
            or published == tkey  # the real board value, even if hidden from the camera
            or (published == prev_visible_key and o.frame - since <= stale_frames)
        )
        if not last_visible:
            ok = True  # nothing seen yet
        if not ok:
            m.wrong_published_frames += 1
            if not wrong_now:
                m.wrong_published += 1
                if len(m.examples) < max_examples:
                    m.examples.append(
                        {"frame": o.frame, "published_wrong": str(published), "expected": str(cur)}
                    )
        wrong_now = not ok

    # 3) changes captured and their delay
    frames = [o.frame for o in obs]
    for i in range(1, len(truth.frames)):
        if not truth.visible[i] or truth.values[i] == truth.values[i - 1]:
            continue
        start = truth.frames[i]
        end = (
            truth.frames[i + 1] if i + 1 < len(truth.frames) else (frames[-1] + 1 if frames else 0)
        )
        target = key_of(f, truth.values[i])
        lo = bisect.bisect_left(frames, start)
        if lo >= len(frames) or frames[lo] >= end:
            continue  # change outside the evaluated frames
        m.changes += 1
        for j in range(lo, len(frames)):
            if frames[j] >= end:
                break
            if published_trace[j] == target:
                m.captured += 1
                m.delays_ms.append((frames[j] - start) / fps * 1000)
                break
    return m
