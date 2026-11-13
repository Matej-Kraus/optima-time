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
tools/                 synth, eval, xml_reader_sim, labeler
spikes/                Milestone 0 one-off experiments — never imported by the product
tests/                 pytest
docs/                  SPEC, PLAN, DECISIONS, BACKLOG, MANUAL_TESTS (+ OPERATOR later)
samples/               photos, recordings, real XML from production (large videos are git-ignored)
```

## Commands

```sh
uv sync                          # install Python deps (dev group by default)
uv sync --group spikes           # + deps for spikes/
uv run pytest                    # tests
uv run ruff check . && uv run ruff format --check .
uv run pyright                   # backend, tests, tools (not spikes/)
cd frontend && npm ci && npm test && npm run lint && npm run build
```

## Conventions

- Python 3.13, pinned versions in `pyproject.toml` (`uv.lock` committed). Frontend versions pinned exactly in `package.json`.
- Time: `time.monotonic_ns()` for measurements; wall-clock time also goes into the event log.
- Between pipeline stages "latest wins": no queue may grow.
- ONNX Runtime: CPU only, few threads (default 1–2), spinning off — vMix runs on the same PC.
