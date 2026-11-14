"""Shadow run helpers (SPEC 15.6): compare our values with the reference app over a real match.

1) sample   Poll the reference app's XML file (the one vMix reads today) every 100 ms and log
            each change with wall-clock time:
              uv run python -m tools.shadow sample --path C:\\vmix\\ref.xml --out ref.jsonl
2) compare  Compare that log with Optima Time's event log of the same match:
              uv run python -m tools.shadow compare ref.jsonl events-2026-11-20.jsonl
            (the event log is in %APPDATA%\\OptimaTime\\logs)

Field names are matched as they are (ours were chosen to equal the reference app's). For each
field the comparison walks both timelines second by second and counts the seconds where the
values differ for longer than --tolerance seconds (a short lag is not a disagreement), and lists
the disagreements to look at. Where the two apps disagree, a recording or the diagnostics
bundle tells who was right.
"""

from __future__ import annotations

import argparse
import bisect
import json
import time
from datetime import datetime
from pathlib import Path

from optima_time.outputs.xml import parse_xml


def sample(path: Path, out: Path, interval: float) -> None:
    last: dict[str, str] = {}
    print(f"sampling {path} every {interval * 1000:.0f} ms -> {out} (Ctrl+C to stop)")
    with out.open("a", encoding="utf-8") as f:
        try:
            while True:
                try:
                    values = parse_xml(path.read_bytes())
                except (OSError, ValueError, SyntaxError):
                    time.sleep(interval)
                    continue
                now = datetime.now().astimezone().isoformat(timespec="milliseconds")
                for field, value in values.items():
                    if last.get(field) != value:
                        f.write(
                            json.dumps(
                                {"wall": now, "field": field, "text": value}, ensure_ascii=False
                            )
                            + "\n"
                        )
                last = values
                f.flush()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("stopped")


def _ts(wall: str) -> float:
    return datetime.fromisoformat(wall.replace("Z", "+00:00")).timestamp()


def load(path: Path, kinds: set[str] | None) -> dict[str, list[tuple[float, str]]]:
    tracks: dict[str, list[tuple[float, str]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if kinds is not None and e.get("kind") not in kinds:
            continue
        if not e.get("field"):
            continue
        tracks.setdefault(e["field"], []).append((_ts(e["wall"]), e.get("text", "")))
    for t in tracks.values():
        t.sort()
    return tracks


def value_at(track: list[tuple[float, str]], t: float) -> str | None:
    i = bisect.bisect_right([x for x, _ in track], t) - 1
    return track[i][1] if i >= 0 else None


def compare(ref: Path, ours: Path, tolerance: float) -> dict:
    a = load(ref, None)
    b = load(ours, {"changed", "held", "cleared"})
    start = max(min(t[0][0] for t in a.values()), min(t[0][0] for t in b.values()))
    end = min(max(t[-1][0] for t in a.values()), max(t[-1][0] for t in b.values()))
    report: dict = {"seconds": round(end - start), "fields": {}}
    for field in sorted(set(a) & set(b)):
        bad_run = 0.0  # how long the two have differed, in seconds
        counted = False  # this disagreement episode is already counted
        disagreements: list[dict] = []
        t = start
        while t <= end:
            va, vb = value_at(a[field], t), value_at(b[field], t)
            if va != vb:
                bad_run += 0.1
                if bad_run > tolerance and not counted:
                    counted = True
                    disagreements.append({"t": round(t - start, 1), "reference": va, "ours": vb})
            else:
                bad_run, counted = 0.0, False
            t += 0.1
        report["fields"][field] = {"disagreements": len(disagreements), "first": disagreements[:10]}
    report["only_in_reference"] = sorted(set(a) - set(b))
    report["only_in_ours"] = sorted(set(b) - set(a))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--path", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--interval", type=float, default=0.1)
    c = sub.add_parser("compare")
    c.add_argument("reference", type=Path)
    c.add_argument("ours", type=Path)
    c.add_argument("--tolerance", type=float, default=1.0, help="seconds of lag allowed")
    args = parser.parse_args()
    if args.cmd == "sample":
        sample(args.path, args.out, args.interval)
        return 0
    report = compare(args.reference, args.ours, args.tolerance)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0 if all(f["disagreements"] == 0 for f in report["fields"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
