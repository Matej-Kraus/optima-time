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

import cv2

from optima_time.config.store import load_profile
from optima_time.pipeline import Pipeline
from optima_time.sources.file import FileSource
from tools.eval.metrics import Observation, evaluate_field, key_of, load_truth


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
    model = profile.fields[0].engine.model if profile.fields else "?"
    min_width = profile.fields[0].engine.min_width if profile.fields else 0
    truth = load_truth(truth_path)
    fields = {f.id: f for f in profile.fields}

    pipeline = Pipeline(profile, threads=args.threads, keep_crops=bool(args.dump_errors))
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
            result = pipeline.process(frame)
            totals.append(result.timings_ms["total"])
            ocr_ms.append(result.timings_ms["ocr"])
            for fid, r in result.fields.items():
                reading = r.reading
                obs[fid].append(
                    Observation(
                        index,
                        r.status,
                        reading.text if reading else "",
                        reading.confidence if reading else 0.0,
                        r.value.key if r.value is not None else None,
                    )
                )
                if args.dump_errors and r.crop is not None and dumped < 300 and fid in truth:
                    text, visible = truth[fid].at(index)
                    got = r.value.key if r.value is not None else None
                    if visible and got != key_of(fields[fid], text):
                        read = reading.text if reading else "gate"
                        name = f"{index:06d}_{fid}_truth-{text or 'blank'}_read-{read or 'none'}"
                        args.dump_errors.mkdir(parents=True, exist_ok=True)
                        cv2.imwrite(str(args.dump_errors / f"{name.replace(':', '-')}.png"), r.crop)
                        dumped += 1
            if index % 500 == 0:
                print(f"  frame {index}  ({time.monotonic() - started:.0f} s)")

    rows = []
    for f in profile.fields:
        if f.id not in truth:
            continue
        m = evaluate_field(f, truth[f.id], obs[f.id], fps)
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
        f"(OCR median {timing['ocr_ms_median']} ms); every field read on every frame "
        f"(change detection comes in Milestone 3)"
    )
    total_wrong = sum(s["wrong_published"] for s, _ in rows)
    print(f"WRONG PUBLISHED VALUES (naive publishing, no confirmation): {total_wrong}")

    report = {
        "video": str(video),
        "model": model,
        "min_width": min_width,
        "threads": args.threads,
        "machine": f"{platform.system()} {platform.machine()}",
        "frames": len(totals),
        "timing": timing,
        "wrong_published_total": total_wrong,
        "fields": [s for s, _ in rows],
        "examples": {s["field"]: ex for s, ex in rows},
    }
    out = truth_path.parent / f"eval_{model}_{min_width}.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
