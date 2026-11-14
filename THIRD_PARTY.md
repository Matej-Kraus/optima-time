# Third-party software and models

| Component | Version | Licence | Use |
|---|---|---|---|
| numpy | 2.5.4 | BSD-3-Clause and others | arrays |
| opencv-python-headless | 5.0.0.93 | Apache-2.0 | image processing, capture devices |
| onnxruntime | 1.32.0 | MIT | running PP-OCR models (CPU) |
| pydantic | 2.14.3 | MIT | configuration models |
| fastapi | 0.162.7 | MIT | API |
| uvicorn | 0.54.0 | BSD-3-Clause | ASGI server |
| cyndilib | 0.1.3 | MIT | NDI receiving |
| cv2-enumerate-cameras | 1.4.0 | MIT | capture device names and OpenCV indices |
| psutil | 7.2.2 | BSD-3-Clause | CPU and memory of the process |
| NDI® runtime (bundled in the cyndilib wheel) | – | NDI SDK licence (`libndi_licenses.txt` in the wheel) | NDI |
| PP-OCRv6_tiny_rec (ONNX) | HF rev `2612ab3…` | Apache-2.0 | text recognition |
| PP-OCRv6_small_rec (ONNX) | HF rev `b8f84f0…` | Apache-2.0 | text recognition |
| pystray (Windows only) | 0.19.5 | LGPL-3.0 | tray icon of the packaged app; used unmodified as a separate module |
| pywebview (Windows only) | 6.2.1 | BSD-3-Clause | the app's own window (Edge WebView2) |
| pythonnet, clr-loader (Windows only, via pywebview) | 3.2.1, 0.3.1 | MIT | .NET bridge for the WebView2 window |
| bottle, proxy-tools (via pywebview) | 0.13.4, 0.1.0 | MIT | pywebview internals |
| Pillow (Windows runtime: tray icon; dev: synth) | 13.0.0 | MIT-CMU | icon image, font rendering in `tools/synth` |
| PyInstaller (build only) | 6.22.3 | GPL-2.0-or-later with the bootloader exception | packaging; the exception allows distributing the bundled app under any terms |
| PyYAML (build/dev only) | 6.0.3 | MIT | reading `inference.yml` in `scripts/fetch_models.py` |
| React, React DOM | 19.3.1 | MIT | UI |
| Chivo, JetBrains Mono fonts (`@fontsource/chivo`, `@fontsource/jetbrains-mono`) | 5.3.0 | SIL OFL 1.1 | UI fonts, bundled so the UI works offline |
| Vite, Vitest, TypeScript, oxlint | see `frontend/package.json` | MIT / Apache-2.0 | UI build and tests |

## Code reused from ScoreSight

ScoreSight (https://github.com/royshil/scoresight) is MIT-licensed. Any file or function taken or adapted from it keeps this header and is listed here:

```text
Adapted from ScoreSight (https://github.com/royshil/scoresight), MIT License,
Copyright (c) 2024 OCC AI: Open tools for Content Creators and Streamers. See THIRD_PARTY.md.
```

| Our file | ScoreSight source | What |
|---|---|---|
| `spikes/ppocr/ppocr_spike.py` | `src/ppocr_engine.py` (rev `8bef5a9`) | preprocessing (`resize_normalize`), greedy CTC with a character whitelist |
| `backend/optima_time/recognizers/ppocr.py` | `src/ppocr_engine.py` (rev `8bef5a9`) | `resize_normalize`, `padded_width`, `class_groups`, greedy CTC, `as_probabilities`, batching by padded width |

## Before distributing outside the company

- NDI®: read the licensing section of the NDI SDK (branding, trademark, URLs to display). "NDI® is a registered trademark of Vizrt NDI AB."
- Model licences (Apache-2.0): include the licence and notice.
- pystray (LGPL-3.0): ship it as a replaceable module (PyInstaller keeps it in the archive as bytecode; a user can rebuild with another version) and include the LGPL text.
