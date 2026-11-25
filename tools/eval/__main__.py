"""Evaluate the pipeline on a recording with ground truth (SPEC 15.3).

Usage:
  uv run python -m tools.eval samples/synth/default
  uv run python -m tools.eval VIDEO --truth truth.jsonl --profile profile.json
Options: --model tiny|small, --min-width N, --threads N, --seconds N, --dump-errors DIR

A recording folder holds match.mp4, truth.jsonl and profile.json (as tools/synth writes them).
Prints a table per field and writes eval_<model>.json next to the truth.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from pathlib import Path

from optima_time.config.models import Deinterlace
from optima_time.config.store import load_profile
from optima_time.imageio import write_image
from optima_time.pipeline import Pipeline
from optima_time.sources.file import FileSource
from optima_time.state import BoardState
from tools.eval.metrics import NAIVE, Observation, evaluate_field, key_of, load_truth


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("recording", type=Path, help="folder, or the video file")
    parser.add_argument("--truth", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--model", choices=["tiny", "small"])
    parser.add_argument("--min-width", type=int)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seconds", type=float, help="evaluate only the first N seconds")
    parser.add_argument("--dump-errors", type=Path, help="save crops of misread frames here")
    parser.add_argument(
        "--naive",
        action="store_true",
        help="naive publishing (Milestone 1 baseline) instead of the app's logic",
    )
    parser.add_argument("--no-guard", action="store_true", help="ignore the layout anchors")
    parser.add_argument(
        "--no-detection",
        action="store_true",
        help="read every field on every frame (no change detection)",
    )
    args = parser.parse_args()

    folder = args.recording if args.recording.is_dir() else args.recording.parent
    video = args.recording if args.recording.is_file() else folder / "match.mp4"
    truth_path = args.truth or folder / "truth.jsonl"
    profile = load_profile(args.profile or folder / "profile.json")
    for f in profile.fields:
        if args.model:
            f.engine.model = args.model
        if args.min_width:
            f.engine.min_width = args.min_width
    if args.no_guard:
        profile.guard.anchors = []
    if args.no_detection:
        profile.detection.enabled = False
    model = profile.fields[0].engine.model if profile.fields else "?"
    min_width = profile.fields[0].engine.min_width if profile.fields else 0
    truth = load_truth(truth_path)
    fields = {f.id: f for f in profile.fields if f.enabled}

    pipeline = Pipeline(profile, threads=args.threads, keep_crops=bool(args.dump_errors))
    state = BoardState(profile)
    ocr_reads = field_frames = 0
    guard_lost = 0
    obs: dict[str, list[Observation]] = {f.id: [] for f in profile.fields}
    totals, ocr_ms = [], []
    dumped = 0
    started = time.monotonic()
    with FileSource(video, loop=False, speed=0, deinterlace_mode=profile.source.deinterlace) as src:
        fps = src.info.fps
        max_frames = int(args.seconds * fps) if args.seconds else None
        while (frame := src.read_latest()) is not None:
            index = frame.seq - 1
            if max_frames is not None and index >= max_frames:
                break
            result = pipeline.process(frame, state.unsettled())
            ocr_reads += int(result.timings_ms.get("ocr_fields", 0))
            field_frames += len(fields)
            totals.append(result.timings_ms["total"])
            ocr_ms.append(result.timings_ms.get("ocr", 0.0))
            guard_lost += not result.guard.ok
            now_ns = round((frame.pts or index / fps) * 1e9)  # media time: eval runs faster
            state.update(result, result.guard, True, now_ns)
            published = state.values()
            for fid, f in fields.items():
                r = result.fields.get(fid)
                reading = r.reading if r else None
                obs[fid].append(
                    Observation(
                        index,
                        r.status if r else None,
                        reading.text if reading else "",
                        reading.confidence if reading else 0.0,
                        r.value.key if r and r.value is not None else None,
                        NAIVE if args.naive else key_of(f, published.get(fid, "")),
                    )
                )
                if args.dump_errors and r and r.crop is not None and dumped < 300 and fid in truth:
                    text, visible = truth[fid].at(index)
                    got = r.value.key if r.value is not None else None
                    if visible and got != key_of(f, text):
                        read = reading.text if reading else "gate"
                        name = f"{index:06d}_{fid}_truth-{text or 'blank'}_read-{read or 'none'}"
                        args.dump_errors.mkdir(parents=True, exist_ok=True)
                        write_image(str(args.dump_errors / f"{name.replace(':', '-')}.png"), r.crop)
                        dumped += 1
            if index % 500 == 0:
                print(f"  frame {index}  ({time.monotonic() - started:.0f} s)")

    rows = []
    for f in profile.fields:
        if f.id not in truth:
            continue
        m = evaluate_field(
            f,
            truth[f.id],
            obs[f.id],
            fps,
            interlaced=profile.source.deinterlace is not Deinterlace.NONE,
        )
        rows.append((m.summary(), m.examples))

    print(
        f"\n{video}  model={model} min_width={min_width} threads={args.threads}  "
        f"frames={len(totals)}"
    )
    header = (
        f"{'field':10} {'crop %':>7} {'lit':>5} {'wrong':>5} {'inval':>5} {'lowc':>5} "
        f"{'blank':>5} {'unlit→v':>7} {'chg':>4} {'capt %':>7} {'dly50':>6} {'dly95':>6} "
        f"{'WRONG PUB':>9}"
    )
    print(header)
    for s, _ in rows:
        print(
            f"{s['field']:10} {s['crop_accuracy_%'] or 0:7.2f} {s['lit_crops']:5} "
            f"{s['wrong_value']:5} {s['invalid']:5} {s['low_conf']:5} {s['blank']:5} "
            f"{s['unlit_read_as_value']:7} {s['changes']:4} {s['captured_%'] or 0:7.2f} "
            f"{s['delay_ms_median'] or 0:6.0f} {s['delay_ms_p95'] or 0:6.0f} "
            f"{s['wrong_published']:9}"
        )
    t = sorted(totals)
    timing = {
        "frame_ms_median": round(statistics.median(t), 2),
        "frame_ms_p95": round(t[int(0.95 * (len(t) - 1))], 2),
        "ocr_ms_median": round(statistics.median(ocr_ms), 2),
    }
    print(
        f"\ntime per frame: median {timing['frame_ms_median']} ms, "
        f"p95 {timing['frame_ms_p95']} ms "
        f"(OCR median {timing['ocr_ms_median']} ms); "
        "(with change detection unless --no-detection)"
    )
    total_wrong = sum(s["wrong_published"] for s, _ in rows)
    mode = "naive publishing" if args.naive else "app logic"
    guard_info = "off" if not profile.guard.anchors else f"{guard_lost} frames lost"
    print(f"layout guard: {guard_info}")
    share = 100 * ocr_reads / max(1, field_frames)
    print(f"OCR reads: {ocr_reads} of {field_frames} field-frames ({share:.1f} %)")
    print(f"WRONG PUBLISHED VALUES ({mode}): {total_wrong}")

    report = {
        "video": str(video),
        "model": model,
        "min_width": min_width,
        "threads": args.threads,
        "publishing": mode,
        "ocr_reads": ocr_reads,
        "ocr_read_share_%": round(share, 2),
        "guard_lost_frames": guard_lost if profile.guard.anchors else None,
        "machine": f"{platform.system()} {platform.machine()}",
        "frames": len(totals),
        "timing": timing,
        "wrong_published_total": total_wrong,
        "fields": [s for s, _ in rows],
        "examples": {s["field"]: ex for s, ex in rows},
    }
    suffix = "_naive" if args.naive else ""
    out = truth_path.parent / f"eval_{model}_{min_width}{suffix}.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
