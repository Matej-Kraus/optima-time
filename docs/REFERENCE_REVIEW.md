# Review of the ScoreSight reference package

Date: 25 November 2026. This document records which parts of the supplied
ScoreSight/Scoreboard OCR reference package are relevant to Optima Time. The
archive itself is intentionally not vendored: it contains duplicate runtime
code, copied documentation and UI screenshots that are useful for comparison
but not required to build or operate the product.

## Product decisions

- Optima Time remains a **floorball** application. The hockey wording and
  PascalCase field examples in the supplied draft are not a second product
  specification.
- Existing profile field ids (`Time`, `scoreh`, `scorea`, `period`,
  `penaltyh1` …) remain stable. XML output gets an optional id-to-element-name
  mapping instead of renaming fields and breaking existing profiles.
- XML file/HTTP Data Source remains the primary vMix integration. TCP 8099
  remains the optional low-latency output. HTTP 8088 is added for read-only
  discovery of vMix titles and their fields.
- Existing profiles keep their current blank behaviour. New floorball
  templates clear a blank penalty after two seconds and treat `0:00` as an
  immediate clear.
- UI ideas are adapted to the existing React application. ScoreSight branding,
  screenshots and its Qt three-panel layout are not copied.

## Keep the existing implementation

The reference package duplicates these mature parts of Optima Time and must not
be imported as a parallel `scoreboard_io` stack:

- latest-frame capture, reconnect and source status in
  `backend/optima_time/sources/`;
- NDI input in `sources/ndi.py`;
- atomic XML writing and retry in `outputs/xml_file.py`;
- latest-wins output workers in `outputs/base.py`;
- persistent vMix TCP output, including image, visibility and colour commands,
  in `outputs/vmix_api.py`;
- PP-OCRv6 preprocessing, masked CTC decoding and batching in
  `recognizers/ppocr.py`;
- confirmation, plausibility, layout anchors, diagnostics and the
  synth/eval/replay/shadow toolchain.

Replacing these modules would create two implementations of the same runtime
rules and would risk regressions without improving the measured product.

## Adapt selectively

The useful gaps, in implementation order, are:

1. Output-name mapping for XML file and HTTP feed, while keeping internal field
   ids stable.
2. Configurable penalty end behaviour: delayed clear on blank and immediate
   clear at zero.
3. Read-only vMix Web API discovery (`GET http://host:8088/api/`) with bounded
   timeouts, XML parsing, actionable errors and UI selectors.
4. Operator feedback: age of the last accepted reading, non-colour-only field
   states, compact output status and confirmations for destructive actions.
5. Capture-card diagnostics (`describe`: actual resolution, fps, FOURCC and
   backend) only if the Windows production test shows that the current
   DirectShow/MSMF controls are insufficient.

Any ScoreSight function adapted in code keeps the attribution header prescribed
by `THIRD_PARTY.md`. Behavioural test cases may be re-expressed in the existing
test suite; the reference package is not imported as a dependency.

## Deferred until evidence exists

- ORB image stabilization: layout anchors already fail safe; add stabilization
  only if a real camera shift is observed.
- automatic tiny/small switching and hybrid confirmation: decide from labelled
  real footage and measurements beside vMix.
- custom regex fields, smoothing, screen capture, generic socket outputs and a
  glyph engine: not required for the floorball production path.
- HTTP SetText output: XML remains primary and TCP already provides push output.
  Add HTTP sending only if a real vMix test exposes a TCP limitation.

## Source and licence boundary

- ScoreSight: <https://github.com/royshil/scoresight>, MIT, copyright 2024 OCC
  AI. The licence text is stored in `LICENSES/ScoreSight-MIT.txt`.
- PP-OCRv6 models: PaddlePaddle, Apache-2.0; revisions and notices are recorded
  in `THIRD_PARTY.md`.
- Scoreboard OCR: only public documentation and observed behaviour may be used.
  Its binaries, files, traffic, branding and UI are outside the clean-room
  boundary.

The supplied screenshots and copied ScoreSight documentation are research
inputs, not product assets. Public documentation may link to the upstream
project instead of republishing those files.
