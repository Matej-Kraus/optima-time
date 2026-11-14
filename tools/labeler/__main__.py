"""Pre-fill ground truth for a real recording from OCR, for a person to correct (SPEC 15.3).

Usage:
  uv run python -m tools.labeler RECORDING.mp4 --profile profile.json --out samples/hala1
Writes to --out:
  truth.draft.jsonl   changes as OCR saw them (same format as tools/synth truth.jsonl)
  review.html         one row per change: the crop, the value, an edit box; "Stáhnout"
                      saves the corrected truth.jsonl (works offline, open it in a browser)
  crops/              the crop images review.html shows

A change enters the draft once two consecutive frames agree on it (to skip one-frame misreads);
the human fixes the rest: wrong values, missed changes, and marks frames where the board showed
something else ("visible": false).
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import cv2

from optima_time.config.store import load_profile
from optima_time.fields.models import BlankPolicy
from optima_time.pipeline import Pipeline, ReadStatus
from optima_time.sources.file import FileSource

AGREE_FRAMES = 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=float)
    args = parser.parse_args()

    profile = load_profile(args.profile)
    fields = {f.id: f for f in profile.fields if f.enabled}
    pipeline = Pipeline(profile, keep_crops=True)
    crops_dir = args.out / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    current: dict[str, str | None] = dict.fromkeys(fields)
    candidate: dict[str, tuple[str, int]] = {}
    blank_since: dict[str, int] = {}
    changes: list[dict] = []
    with FileSource(
        args.video, loop=False, speed=0, deinterlace_mode=profile.source.deinterlace
    ) as src:
        fps = src.info.fps
        while (frame := src.read_latest()) is not None:
            i = frame.seq - 1
            if args.seconds and i >= args.seconds * fps:
                break
            result = pipeline.process(frame)
            for fid, r in result.fields.items():
                f = fields[fid]
                value: str | None = None
                if r.status is ReadStatus.VALID and r.value is not None:
                    value = r.value.board
                    blank_since.pop(fid, None)
                elif r.status is ReadStatus.BLANK:
                    start = blank_since.setdefault(fid, i)
                    if (
                        f.blank is BlankPolicy.CLEAR
                        and (i - start) / fps * 1000 >= f.blank_delay_ms
                    ):
                        value = ""
                if value is None or value == current[fid]:
                    candidate.pop(fid, None)
                    continue
                seen, count = candidate.get(fid, (value, 0))
                count = count + 1 if seen == value else 1
                candidate[fid] = (value, count)
                if count >= AGREE_FRAMES:
                    first = i - count + 1
                    current[fid] = value
                    candidate.pop(fid, None)
                    name = f"{first:06d}_{fid}.png"
                    if r.crop is not None:
                        cv2.imwrite(str(crops_dir / name), r.crop)
                    changes.append(
                        {
                            "frame": first,
                            "t": round(first / fps, 3),
                            "field": fid,
                            "value": value,
                            "visible": True,
                            "crop": f"crops/{name}",
                        }
                    )
            if i % 1000 == 0:
                print(f"  frame {i}, {len(changes)} changes")

    with (args.out / "truth.draft.jsonl").open("w", encoding="utf-8") as out:
        for c in changes:
            out.write(
                json.dumps({k: v for k, v in c.items() if k != "crop"}, ensure_ascii=False) + "\n"
            )
    (args.out / "review.html").write_text(review_page(changes), encoding="utf-8")
    print(
        f"{len(changes)} changes -> {args.out / 'truth.draft.jsonl'}; "
        f"open {args.out / 'review.html'} to correct them"
    )
    return 0


def review_page(changes: list[dict]) -> str:
    rows = "\n".join(
        f'<tr data-i="{n}"><td>{c["frame"]}</td><td>{c["t"]:.2f}</td>'
        f'<td>{html.escape(c["field"])}</td><td><img src="{html.escape(c["crop"])}"></td>'
        f'<td><input value="{html.escape(c["value"])}"></td>'
        f'<td><input type="checkbox" checked title="viditelné"></td>'
        f'<td><input type="checkbox" title="smazat"></td></tr>'
        for n, c in enumerate(changes)
    )
    data = json.dumps(changes, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8"><title>Kontrola pravdy</title>
<style>
body{{font-family:system-ui,sans-serif;background:#111418;color:#e8eaed;margin:16px}}
table{{border-collapse:collapse}} td,th{{border-bottom:1px solid #2c333c;padding:4px 8px}}
img{{height:40px;image-rendering:pixelated}} input{{font:inherit;width:7em}}
button{{font:inherit;padding:6px 12px;margin:8px 0}}
</style></head><body>
<h1>Kontrola pravdy</h1>
<p>Oprav hodnoty, které OCR přečetlo špatně (prázdné = zhasnuté pole). Odškrtni „viditelné“,
když tabule v tu chvíli ukazovala něco jiného. Chybějící změnu dopiš do souboru ručně.
Pak klikni na „Stáhnout truth.jsonl“ a ulož ho vedle záznamu.</p>
<button id="save">Stáhnout truth.jsonl</button>
<table><thead><tr><th>snímek</th><th>čas [s]</th><th>pole</th><th>výřez</th><th>hodnota</th>
<th>viditelné</th><th>smazat</th></tr></thead><tbody>
{rows}
</tbody></table>
<script>
const changes = {data};
document.getElementById("save").onclick = () => {{
  const lines = [];
  document.querySelectorAll("tbody tr").forEach((tr) => {{
    const c = changes[+tr.dataset.i];
    const [value, visible, del] = tr.querySelectorAll("input");
    if (del.checked) return;
    lines.push(JSON.stringify({{frame: c.frame, t: c.t, field: c.field,
                               value: value.value, visible: visible.checked}}));
  }});
  const blob = new Blob([lines.join("\\n") + "\\n"], {{type: "application/json"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "truth.jsonl";
  a.click();
}};
</script></body></html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
