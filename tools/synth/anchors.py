"""Add layout-guard anchors (the static captions) to a synthetic recording's profile.

The templates are captured from the recording's first frame, as an operator would do in the UI.
Usage: uv run python -m tools.synth.anchors samples/synth/default
"""

from __future__ import annotations

import argparse
from pathlib import Path

from optima_time.config.models import AnchorConfig
from optima_time.config.store import load_profile, save_profile
from optima_time.fields.models import Roi
from optima_time.geometry import Rectifier
from optima_time.guard import capture_template
from optima_time.sources.file import FileSource
from tools.synth.board import COLS, LABELS, ROWS


def add_anchors(folder: Path) -> None:
    path = folder / "profile.json"
    profile = load_profile(path)
    with FileSource(folder / "match.mp4", loop=False, speed=0) as src:
        frame = src.read_latest()
        assert frame is not None, "empty recording"
    geo = profile.geometry
    h, w = frame.image.shape[:2]
    rectified = Rectifier.create(geo.corners, (w, h), geo.rotate, geo.max_width, geo.aspect).warp(
        frame.image
    )
    anchors = []
    for x, y, bw, bh in LABELS.values():
        roi = Roi(x=x / COLS, y=y / ROWS, w=bw / COLS, h=bh / ROWS)
        anchors.append(AnchorConfig(roi=roi, template=capture_template(rectified, roi)))
    profile.guard.anchors = anchors
    save_profile(profile, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("folders", type=Path, nargs="+")
    for folder in parser.parse_args().folders:
        add_anchors(folder)
        print(f"anchors added: {folder / 'profile.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
