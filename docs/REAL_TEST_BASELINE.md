# Real-recording baseline (casomira-1, 2026-11-25)

Recording (local only, git-ignored): `/Users/mates/Optima_time/samples/real/casomira-1.mp4`
— 1280×720, 25 fps, 24.2 min, first period SLO–NOR.

| Artifact | Path |
|---|---|
| Profile | `samples/real/profile.json` |
| OCR draft truth (not hand-corrected) | `samples/real/truth.jsonl` |
| Replay report | `samples/real/replay-report.txt` |
| Eval tiny | `samples/real/eval_tiny_160.json` |

## Replay (`tools.replay`) — physics check

| Metric | Result |
|---|---|
| Frames | 36 300 |
| Processing | median 10.4 ms, p95 31.5 ms |
| Layout guard lost | 0 frames |
| Time changes | 1200, last `19:59` |
| scorea | 3 → `2` |
| penaltya1 | 121, ends empty |
| Suspicious changes | **0** |

## Eval tiny vs OCR draft truth

| Field | Capture % | Wrong published |
|---|---|---|
| Time | 100 % of 1198 changes | **1** (`02:16` vs draft `02:15` @ frame 4386) |
| scorea | 100 % of 2 | 0 |
| penaltya1 | 100 % of 121 | 0 |
| period / scoreh | no changes in draft | 0 |

OCR crop mismatches on Time exist in the draft (e.g. `03:80`, `04:00` vs `04:09`); confirmation logic held them. The single wrong publish is one second early versus the **uncorrected** OCR draft — treat it as a labeling suspect until `review.html` is corrected by hand.

Frame time: median 8.0 ms, p95 20.1 ms; OCR on 2.9 % of field-frames; guard lost 0.

## Coverage gaps (need another recording)

- home / second penalty slots
- period change and overtime
- last-minute tenths (`ss.d`)
- full-board animation over anchors

## Next

1. Hand-correct `truth.jsonl` via `tools.labeler` → `review.html`.
2. Re-run `tools.eval` for tiny and small.
3. Production PC: `docs/WINDOWS_VALIDATION.md`.
