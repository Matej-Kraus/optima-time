# optima-time

Reads a physical LED scoreboard (floorball) from video in real time — clock, score, period, penalties — and writes the values to an XML file that vMix reads as a Data Source. Full brief: `docs/SPEC.md` (Czech). Current plan: `docs/PLAN.md`.

## Working rules (from SPEC 16.2, short)

- Talk to Matěj in **Czech**. Code, identifiers, comments, commits in **English**. UI texts in Czech, kept in one place.
- Plan first, then code. Stop after each milestone and wait for approval.
- Small verified steps: run tests + lint after each change. Never claim something works without running it. What can't be verified here (real vMix, NDI, production PC) goes to `docs/MANUAL_TESTS.md`.
- Nothing extra: ideas outside the current milestone → `docs/BACKLOG.md`.
- Decisions → `docs/DECISIONS.md`. Third-party code/licences → `THIRD_PARTY.md`.
- Clean-room: never decompile or inspect Scoreboard OCR. ScoreSight (MIT) may be read and reused with attribution.
- Fail safe: when in doubt, hold the last valid value. An invalid value never leaves the process.
- Core must run and be tested on macOS/Linux; Windows-only sources sit behind an interface.

## Layout

```text
backend/optima_time/   the product (Python package)
frontend/              React + TypeScript + Vite, built to static files served by the backend
                       src/views: Live / Setup / Diagnostics tabs; texts in src/i18n/cs.ts
tools/                 synth, eval, labeler, bench, xml_reader_sim, shadow
packaging/             PyInstaller spec, launcher, Inno Setup installer (.iss), icon
.github/workflows/     CI: tests on Windows + macOS, Windows package + installer (artifact)
spikes/                Milestone 0 one-off experiments — never imported by the product
tests/                 pytest
docs/                  SPEC, PLAN, DECISIONS, BACKLOG, MANUAL_TESTS, OPERATOR, M*_REPORT
samples/               photos, recordings, real XML from production (large videos are git-ignored)
```

## Commands

```sh
uv sync                                   # Python deps (dev group by default)
uv run python scripts/fetch_models.py     # PP-OCR models -> models/ppocr/ (once; git-ignored)
uv run pytest                             # tests (model tests skip without models)
uv run ruff check . && uv run ruff format --check .
uv run pyright                            # backend, tests, tools (not spikes/)
cd frontend && npm ci && npm test && npm run lint && npm run build   # build before `run`

# run the app on a recording (UI at http://127.0.0.1:8787, serves frontend/dist)
uv run optima-time run --profile samples/synth/short/profile.json
# frontend dev server with hot reload (proxies /api to :8787)
cd frontend && npm run dev

# synthetic recording + ground truth + ready profile, then evaluate it
uv run python -m tools.synth --out samples/synth/default [--hard] [--short] [--interlaced]
uv run python -m tools.eval samples/synth/default [--model small] [--min-width 320] [--dump-errors DIR]
# pre-fill ground truth for a real recording (review.html to correct it)
uv run python -m tools.labeler VIDEO --profile PROFILE --out DIR
# performance (latency frame -> XML, CPU, memory) and the stress test
uv run python -m tools.bench samples/synth/default --seconds 60 [--hours 3 --out stress.jsonl]
# vMix-like XML reader against our writer
uv run python -m tools.xml_reader_sim --with-writer --emulate-lock --minutes 1
# shadow run: sample the reference app's XML, compare with our event log
uv run python -m tools.shadow sample --path REF.xml --out ref.jsonl
uv run python -m tools.shadow compare ref.jsonl events-YYYY-MM-DD.jsonl
# installation check, packaging
uv run optima-time --self-test
uv run pyinstaller packaging/optima-time.spec --noconfirm --distpath build/dist --workpath build/work
powershell -File scripts\build_windows.ps1   # Windows: tests, package, self-test, zip
OPTIMA_TIME_NDI_TEST=1 uv run pytest tests/test_ndi.py   # NDI end to end (local sender)
```

## Conventions

- Python 3.13, pinned versions in `pyproject.toml` (`uv.lock` committed). Frontend versions pinned exactly in `package.json`.
- Time: `time.monotonic_ns()` for measurements; wall-clock time also goes into the event log.
- Between pipeline stages "latest wins": no queue may grow.
- ONNX Runtime: CPU only, few threads (default 1–2), spinning off — vMix runs on the same PC.
- Field values: `fields/formats.py` (pure parse/render), field types in `fields/models.py` (Pydantic, discriminated by `type`), each with `parse()`/`render()`.
- Relative coordinates everywhere in profiles: corners relative to the source frame, ROIs relative to the rectified board.
- OpenCV returns `MatLike`; wrap with `np.asarray(..., np.uint8)` where a typed `ndarray` is needed (pyright).
- tools/ are run as modules from the repo root (`python -m tools.eval`); pytest has `pythonpath = ["."]`.

## CI and Windows

- GitHub (private): `Matej-Kraus/optima-time`. Every push runs tests on Windows and macOS and builds the Windows zip + installer (`gh run download` to get them).
- Windows specifics found by CI: console output must be UTF-8 (`cli.utf8_console`); a file being replaced can't be opened for a moment (DECISIONS D29), so tests read XML with retries (`tests/xmlread.py`).
- Timing-based tests must tolerate slow CI machines (assert behaviour, not exact counts).
