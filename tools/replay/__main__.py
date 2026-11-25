"""Replay a real recording through the whole app (pipeline + confirmation) and check what it
would have published, without ground truth (SPEC 15.3).

Usage:
  uv run python -m tools.replay RECORDING.mp4 --profile profile.json --out DIR [--seconds N]
Writes to --out:
  published.jsonl   every published change: media time, field, value
  report.txt        per field: changes, steps that don't fit, guard and timing summary
  suspects/         the field's crop at each suspicious change (to look at by eye)

What counts as suspicious (a real board can't do it):
  clock fields      a step other than ±1 s (±0.1 s with tenths) between consecutive values,
                    except to/from blank (penalty starts/ends) and the period break reset
  number fields     a score going down, or up by more than 1
  period            anything but +1
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from optima_time.config.store import load_profile
from optima_time.fields.models import ClockField, NumberField, PeriodField
from optima_time.imageio import write_image
from optima_time.pipeline import Pipeline
from optima_time.sources.file import FileSource
from optima_time.state import BoardState


def clock_seconds(text: str) -> float | None:
    """'12:02' -> 722.0, '0:42.5' -> 42.5, '' -> None."""
    if not text:
        return None
    try:
        main, _, frac = text.partition(".")
        parts = [int(p) for p in main.split(":")]
        value = 0.0
        for p in parts:
            value = value * 60 + p
        return value + (float("0." + frac) if frac else 0.0)
    except ValueError:
        return None


def suspicious(field, old: str, new: str) -> str | None:
    """Why a change from `old` to `new` can't happen on a real board, or None."""
    if not old or not new:
        return None  # appear / disappear
    if isinstance(field, ClockField):
        a, b = clock_seconds(old), clock_seconds(new)
        if a is None or b is None:
            return "unparsable"
        step = round(b - a, 1)
        ok = {1.0, -1.0, 0.1, -0.1} if field.tenths else {1.0, -1.0}
        if field.tenths and (a < 60 or b < 60):
            ok |= {0.1, -0.1, 0.2, -0.2}
        if step in ok or b == 0 or a == 0:
            return None
        return f"step {step:+g} s"
    if isinstance(field, (NumberField, PeriodField)):
        try:
            a, b = int(old), int(new)
        except ValueError:
            return None  # period names
        if isinstance(field, PeriodField):
            return None if b == a + 1 else f"period {a}->{b}"
        if b < a:
            return f"score down {a}->{b}"
        if b > a + 1:
            return f"score jump {a}->{b}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--start", type=float, default=0.0, help="skip the first N seconds")
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()

    profile = load_profile(args.profile)
    fields = {f.id: f for f in profile.fields if f.enabled}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "suspects").mkdir(exist_ok=True)
    pipeline = Pipeline(profile, threads=args.threads, keep_crops=True)
    state = BoardState(profile)
    last: dict[str, str] = {}
    changes: Counter[str] = Counter()
    suspects: list[str] = []
    guard_lost = frames = 0
    totals: list[float] = []
    started = time.monotonic()
    log = (args.out / "published.jsonl").open("w", encoding="utf-8")
    with FileSource(
        args.video, loop=False, speed=0, deinterlace_mode=profile.source.deinterlace
    ) as src:
        fps = src.info.fps
        first = int(args.start * fps)
        end = first + int(args.seconds * fps) if args.seconds else None
        while (frame := src.read_latest()) is not None:
            index = frame.seq - 1
            if index < first:
                continue
            if end is not None and index >= end:
                break
            frames += 1
            result = pipeline.process(frame, state.unsettled())
            totals.append(result.timings_ms["total"])
            guard_lost += not result.guard.ok
            t = frame.pts if frame.pts is not None else index / fps
            state.update(result, result.guard, True, round(t * 1e9))
            for fid, value in state.values().items():
                if fid not in fields or last.get(fid) == value:
                    continue
                old = last.get(fid)
                last[fid] = value
                if old is None:
                    continue
                changes[fid] += 1
                stamp = f"{int(t // 60)}:{t % 60:04.1f}"
                log.write(json.dumps({"t": round(t, 2), "field": fid, "value": value}) + "\n")
                why = suspicious(fields[fid], old, value)
                if why:
                    suspects.append(f"{stamp:>8}  {fid:<10} {old!r:>8} -> {value!r:<8} {why}")
                    r = result.fields.get(fid)
                    if r is not None and r.crop is not None:
                        name = f"{index:06d}_{fid}_{old}_to_{value}".replace(":", "-")
                        write_image(str(args.out / "suspects" / f"{name}.png"), r.crop)
            if frames % 2500 == 0:
                print(f"  {t / 60:5.1f} min  ({time.monotonic() - started:.0f} s)", flush=True)
    log.close()

    totals.sort()
    lines = [
        f"{args.video}  profile {args.profile}",
        f"frames {frames} ({frames / fps / 60:.1f} min at {fps:g} fps), "
        f"processing median {totals[len(totals) // 2]:.1f} ms, "
        f"p95 {totals[int(0.95 * (len(totals) - 1))]:.1f} ms",
        f"layout guard lost: {guard_lost} frames ({100 * guard_lost / max(1, frames):.1f} %)",
        "",
        "published changes per field:",
        *[f"  {fid:<10} {changes[fid]:6}   last {last.get(fid, '')!r}" for fid in fields],
        "",
        f"suspicious changes: {len(suspects)}",
        *suspects,
    ]
    (args.out / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
