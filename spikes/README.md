# Spikes (Milestone 0)

One-off experiments. Not product code: nothing here is imported by `backend/`. Procedures for the Windows/vMix parts: `docs/MANUAL_TESTS.md`.

| Spike | Script | Question |
|---|---|---|
| A | `ppocr/fetch_models.py`, `ppocr/ppocr_spike.py` | How accurate and fast is PP-OCRv6 tiny/small on scoreboard crops? |
| B | `xml_writer/xml_writer_spike.py` | Does real vMix read an XML file rewritten 10×/s (and the same XML over HTTP) without errors or blank flashes? |
| C | `ndi/ndi_spike.py` (+ `ndi_test_sender.py`) | What does vMix send over NDI (resolution, fps, interlace) and what does receiving cost? |

## Spike A on real photos: `samples/crops.json`

Boxes are pixel rectangles `[x, y, width, height]` in the original photo. Draw them with a little room around the text, as a user would.

```json
[
  {
    "image": "IMG_0001.jpg",
    "fields": [
      {"type": "clock",  "rect": [812, 140, 300, 110], "truth": "12:45", "tag": "clock mm:ss"},
      {"type": "number", "rect": [120, 610, 120, 120], "truth": "3",     "tag": "score"},
      {"type": "period", "rect": [930, 420, 70, 90],   "truth": "2",     "tag": "period"},
      {"type": "clock",  "rect": [100, 480, 160, 70],  "truth": "",      "tag": "unlit"}
    ]
  }
]
```

`truth: ""` marks an unlit or blank field, which must not be read as a digit. Image paths are relative to the JSON file.
