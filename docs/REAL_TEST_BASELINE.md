# Real-recording baseline (casomira-1, 2026-11-25)

Recording (local only, git-ignored): `/Users/mates/Optima_time/samples/real/casomira-1.mp4`
— 1280×720, 25 fps, 24.2 min, first period SLO–NOR.

| Artifact | Path |
|---|---|
| Profile | `samples/real/profile.json` |
| OCR draft truth (2 end-of-clip glitches removed) | `samples/real/truth.jsonl` |
| Eval report (tiny, min_width 160) | `samples/real/eval_tiny_160.json` |
| Regenerable replay/eval working dir | `samples/real/eval/` (git-ignored) |

Truth was pre-filled by `tools.labeler` (1 329 changes → 1 327 kept). It is **not** a full
hand review of every crop; the two dropped Time rows were OCR junk after `19:59`
(`10:00` / `09:59`). Open `build/real-label/review.html` locally if you want to correct more.

## Replay (`tools.replay`)

| Metric | Result |
|---|---|
| Frames | 36 300 |
| Processing | median 11.3 ms, p95 32.6 ms (Mac M-series, concurrent with eval) |
| Layout guard lost | 0 frames |
| Time changes | 1 200, last `19:59` |
| period | 1 → `1` |
| scoreh | 1 → `0` |
| scorea | 3 → `2` (goals at ~9:44 and ~21:38 of the recording) |
| penaltyh1 | 0 (no home penalty this period) |
| penaltya1 | 121, ends empty |
| Suspicious changes | **0** |

Same conclusion as `docs/REAL_TEST_1.md`. Thresholds were not tuned.

## Eval (`tools.eval --model tiny`)

| Field | Crop accuracy | Changes captured | Wrong published |
|---|---:|---:|---:|
| Time | 99.95 % | 100 % of 1 198 | **1** |
| period | 100 % | — (no change) | 0 |
| scoreh | 100 % | — | 0 |
| scorea | 100 % | 100 % of 2 | 0 |
| penaltyh1 | — (dark) | — | 0 |
| penaltya1 | 99.73 % | 100 % of 121 | 0 |

- Frame time: median 10.9 ms, p95 32.1 ms; OCR ran on 2.9 % of field-frames.
- Layout guard: 0 frames lost.
- The single wrong publish is Time at frame 4386: published `02:16` while draft truth
  still said `02:15` (one-second early vs draft). Confirmation held the end-of-clip
  OCR misreads (`19:59` → `10:00` / `09:59`) and did **not** publish them.
- MVP target (SPEC 15.6): 0 wrong publishes, ≥ 99 % changes. Capture is met; the one
  Time mismatch needs a hand-checked truth before treating it as a product defect.

## Coverage gaps (need another recording)

- simultaneous / home `penaltyh2` / `penaltya2`
- period change (2 / OT)
- last-minute tenths (`ss.d`)
- full-board animation covering anchors

## Next

1. Spot-check `review.html` around frame 4386 and the end of the clip; save a corrected
   `truth.jsonl` if the draft is wrong there.
2. Optional: `uv run python -m tools.eval samples/real/eval --model small`.
3. Decide tiny vs small from the production PC (`docs/WINDOWS_VALIDATION.md` §5).
4. Run the Windows/vMix checklist before cutting over Scoreboard OCR.
