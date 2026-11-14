"""Performance and endurance measurement (SPEC 14.4, 15.5).

Runs the whole app (file source in real time -> pipeline -> state -> XML file) on a recording and
measures what matters on the production PC:
  - latency from a frame's arrival to the XML file being replaced (p50, p95, max), for frames
    that changed a published value
  - processing rate vs. source rate, dropped frames
  - process CPU (% of one core and of the whole machine) and memory (RSS)
  - in --hours mode (stress test): the same sampled every minute, plus thread restarts, to show
    that nothing dies, leaks or slows down

Usage:
  uv run python -m tools.bench samples/synth/default --seconds 120
  uv run python -m tools.bench samples/synth/default --hours 3 --out bench_3h.jsonl
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import tempfile
import time
from pathlib import Path

import psutil

from optima_time.config.models import OutputsConfig, XmlFileOutput
from optima_time.config.store import load_profile
from optima_time.runner import Runner


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return round(s[int(q * (len(s) - 1))], 1)


def sample(runner: Runner, proc: psutil.Process, since_cpu: float, since_wall: float) -> dict:
    snap = runner.snapshot()
    src = runner.source_status()
    w = runner.hub.workers[0].status if runner.hub.workers else None
    cpu = proc.cpu_times()
    cpu_s = cpu.user + cpu.system - since_cpu
    wall = time.monotonic() - since_wall
    return {
        "t": round(time.monotonic(), 1),
        "processing_fps": round(snap.processing_fps, 1),
        "source_fps": src.get("fps"),
        "received": src.get("received"),
        "dropped": src.get("dropped"),
        "cpu_percent_one_core": round(100 * cpu_s / wall, 1) if wall else None,
        "cpu_percent_machine": round(100 * cpu_s / wall / (psutil.cpu_count() or 1), 1)
        if wall
        else None,
        "rss_mb": round(proc.memory_info().rss / 2**20, 1),
        "threads": proc.num_threads(),
        "writes": w.writes if w else 0,
        "write_failures": w.failures if w else 0,
        "slow_writes": w.slow_writes if w else 0,
        "latency_ms_p50": pct(list(w.latencies_ms), 0.5) if w else None,
        "latency_ms_p95": pct(list(w.latencies_ms), 0.95) if w else None,
        "latency_ms_max": round(max(w.latencies_ms), 1) if w and w.latencies_ms else None,
        "supervisor_restarts": runner.supervisor.restarts,
        "pipeline_alive": runner.pipeline_alive(),
        "outputs_alive": all(x.alive() for x in runner.hub.workers),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("recording", type=Path, help="folder with match.mp4 and profile.json")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--hours", type=float, help="stress test: loop the recording this long")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--model", choices=["tiny", "small"])
    parser.add_argument("--no-detection", action="store_true")
    parser.add_argument("--out", type=Path, help="JSONL with one sample per minute")
    args = parser.parse_args()

    profile = load_profile(args.recording / "profile.json")
    profile.source.path = str((args.recording / "match.mp4").resolve())
    profile.source.loop, profile.source.speed = True, 1.0
    if args.model:
        for f in profile.fields:
            f.engine.model = args.model
    if args.no_detection:
        profile.detection.enabled = False
    xml = Path(tempfile.mkdtemp(prefix="optima_bench_")) / "tabule.xml"
    profile.outputs = OutputsConfig(xml_file=XmlFileOutput(path=str(xml)))

    duration = args.hours * 3600 if args.hours else args.seconds
    every = 60.0 if args.hours else max(5.0, duration / 6)
    runner = Runner(profile, None, threads=args.threads)
    proc = psutil.Process()
    print(f"bench: {duration:.0f} s, {args.recording}, xml {xml}")
    runner.start()
    t0 = time.monotonic()
    samples: list[dict] = []
    out = args.out.open("w", encoding="utf-8") if args.out else None
    try:
        time.sleep(5)  # warm-up: model load, first confirmations
        runner.hub.workers[0].status.latencies_ms.clear()
        warm_cpu, warm_t = sum(proc.cpu_times()[:2]), time.monotonic()
        last_cpu, last_t = warm_cpu, warm_t
        while time.monotonic() - t0 < duration:
            time.sleep(min(every, max(0.1, duration - (time.monotonic() - t0))))
            s = sample(runner, proc, last_cpu, last_t)
            last_cpu, last_t = sum(proc.cpu_times()[:2]), time.monotonic()
            s["elapsed_s"] = round(time.monotonic() - t0)
            samples.append(s)
            if out:
                out.write(json.dumps(s) + "\n")
                out.flush()
            print(
                f"  {s['elapsed_s']:6d} s  fps {s['processing_fps']}/{s['source_fps']}  "
                f"cpu {s['cpu_percent_one_core']} %  rss {s['rss_mb']} MB  "
                f"lat p95 {s['latency_ms_p95']} ms  dropped {s['dropped']}  "
                f"restarts {s['supervisor_restarts']}"
            )
        total = sample(runner, proc, warm_cpu, warm_t)
    finally:
        runner.stop()
        if out:
            out.close()

    rss = [s["rss_mb"] for s in samples]
    p95s = [s["latency_ms_p95"] for s in samples if s["latency_ms_p95"] is not None]
    report = {
        "machine": f"{platform.system()} {platform.machine()} {platform.processor()}",
        "cpu_count": psutil.cpu_count(),
        "duration_s": round(time.monotonic() - t0),
        "recording": str(args.recording),
        "model": profile.fields[0].engine.model if profile.fields else None,
        "threads": args.threads,
        "detection": profile.detection.enabled,
        "overall": total,
        "rss_mb_first_last_max": [rss[0], rss[-1], max(rss)] if rss else None,
        "latency_p95_first_last": [p95s[0], p95s[-1]] if p95s else None,
        "latency_p95_median_over_samples": statistics.median(p95s) if p95s else None,
    }
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
