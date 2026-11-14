import json
from pathlib import Path

from tools.shadow.__main__ import compare


def write(path: Path, rows: list[tuple[str, str, str]], kind: bool) -> None:
    with path.open("w", encoding="utf-8") as f:
        for wall, field, text in rows:
            e = {"wall": wall, "field": field, "text": text}
            if kind:
                e["kind"] = "changed"
            f.write(json.dumps(e) + "\n")


def test_lag_within_tolerance_is_agreement_but_wrong_value_is_not(tmp_path: Path) -> None:
    t = "2026-11-20T18:00:{:02d}.{:03d}+01:00"
    ref = [
        (t.format(0, 0), "scoreh", "1"),
        (t.format(10, 0), "scoreh", "2"),
        (t.format(30, 0), "scoreh", "2"),
    ]
    ours = [
        (t.format(0, 200), "scoreh", "1"),
        (t.format(10, 400), "scoreh", "2"),  # 0.4 s late
        (t.format(20, 0), "scoreh", "7"),
        (t.format(25, 0), "scoreh", "2"),  # 5 s wrong
        (t.format(30, 0), "scoreh", "2"),
    ]
    write(tmp_path / "ref.jsonl", ref, kind=False)
    write(tmp_path / "ours.jsonl", ours, kind=True)
    report = compare(tmp_path / "ref.jsonl", tmp_path / "ours.jsonl", tolerance=1.0)
    assert report["fields"]["scoreh"]["disagreements"] == 1
    first = report["fields"]["scoreh"]["first"][0]
    assert first["reference"] == "2" and first["ours"] == "7"
