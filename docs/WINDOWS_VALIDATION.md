# Windows / vMix validation checklist

Run this on the production Windows PC with vMix. Send the answers and any
logs/screenshots back; local development continues from those results.

Install the latest CI artifact from PR #14 (`cursor/live-safety-ui`) or merge
to `main` first: `OptimaTime-Setup-0.2.x.exe` from the `package` job.

## 1. Install (M5-A) — 15 min

1. Install the setup exe; launch Optima Time.
2. Confirm the WebView window opens and the tray icon appears.
3. Run:

```powershell
& "$env:LOCALAPPDATA\Programs\OptimaTime\optima-time.exe" --self-test
```

Pass: every check green, no crash, PC does not sleep while running.

## 2. XML Data Source (M0-B / M2-A) — 30 min

1. Create a **copy** of the on-air title (`TEST tabule`), never the production one.
2. Point Optima Time at a non-production XML path, e.g. `C:\vmix-data\optima_test.xml`.
3. In vMix Data Sources → XML:
   - path = that file
   - XPath `/root`
   - refresh **100 ms** (write the lowest available interval)
4. Map `Time`, `scoreh`, `scorea`, `period`, `penaltyh1`, `penaltya1`.
5. Run 10 minutes from a file loop, then 10 minutes live/NDI if available.
6. Also try HTTP: `http://127.0.0.1:8787/data/values.xml`.

Record:

- any vMix file-lock errors
- any blank flashes on score/clock
- whether HTTP or file is more stable

## 3. vMix discovery + TCP (M0-D) — 15 min

1. Enable Web Controller on port **8088** (API without login).
2. In Setup → outputs → vMix API: host `127.0.0.1`, click **Načíst pole**.
3. Pick the test title from the dropdown; map fields; enable TCP **8099**.
4. Change a held value and confirm the title updates.
5. Intentionally map a wrong field name; confirm the UI shows the refused field
   and the other fields keep updating.

## 4. NDI beside vMix (M0-C / M3-A) — 30 min

1. In vMix, NDI-output the scoreboard camera/input.
2. In Optima Time choose that NDI source; run ≥10 minutes with vMix on-air.
3. Record CPU %, RSS MB, processing fps, dropped frames, whether vMix dropped.

Optional: compare DirectShow device open with FOURCC/resolution/fps set.

## 5. PP-OCR tiny vs small (M0-A) — 5 min

With vMix under normal load:

```powershell
uv run python spikes/ppocr/ppocr_spike.py --synthetic 300 --min-width 320 160
```

Send `spikes/ppocr/out/synthetic*_report.json` and the CPU model.

## 6. New hall ≤10 min (M4-A) — 15 min

Follow `docs/OPERATOR.md` from an empty profile on the real board or
`casomira-1.mp4`. Time the steps. Note anything unclear.

## 7. Shadow match (M5-B) — full match

1. Keep Scoreboard OCR writing its XML.
2. Run Optima Time in parallel to another XML/HTTP path.
3. After the match:

```powershell
uv run python -m tools.shadow sample --path REF.xml --out ref.jsonl
uv run python -m tools.shadow compare ref.jsonl events-YYYY-MM-DD.jsonl
```

Cut over only after discrepancies are understood and <1 s on clocks.

## What to send back

For each section: pass/fail, timings, CPU/RAM, screenshots of problems, and the
JSON/log files named above.
