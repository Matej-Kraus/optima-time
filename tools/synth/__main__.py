"""Synthetic scoreboard recordings with ground truth (SPEC 15.2).

Writes to --out:
  match.mp4     the camera's view of the LED wall
  truth.jsonl   ground truth: one line per change of a field's board text or visibility
  profile.json  a ready profile (corners, field ROIs and formats) for this recording
  meta.json     parameters

truth.jsonl lines:
  {"frame": 0, "t": 0.0, "field": "Time", "value": "23:54", "visible": true}
"value" is the board text ("" = unlit); "visible": false while the field can't be seen
(goal animation, a person in front of it). The state holds until the field's next line.

Usage:
  uv run python -m tools.synth --out samples/synth/default
  uv run python -m tools.synth --out samples/synth/hard --hard --seed 2
  uv run python -m tools.synth --out samples/synth/short --short
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from optima_time.config.models import Deinterlace, GeometryConfig, Profile, SourceConfig
from optima_time.config.store import save_profile
from optima_time.fields.formats import ClockStyle
from optima_time.fields.models import (
    BlankPolicy,
    ClockField,
    FieldBase,
    NumberField,
    PeriodField,
    Roi,
)
from tools.synth.anchors import add_anchors
from tools.synth.board import (
    BOXES,
    COLS,
    HARD,
    ROWS,
    Camera,
    CameraStyle,
    LedStyle,
    foreign_board,
    led_board,
    weave,
)
from tools.synth.timeline import FIELDS, Timeline, simulate

CROP_MARGIN = FieldBase.model_fields["margin"].default  # the pipeline's default crop margin


def roi(name: str) -> Roi:
    x, y, w, h = BOXES[name]
    return Roi(x=x / COLS, y=y / ROWS, w=w / COLS, h=h / ROWS)


def make_profile(cam: CameraStyle, video: Path, interlaced: bool) -> Profile:
    fields = [
        ClockField(
            id="Time", label="Čas", roi=roi("Time"), tenths=True, style=ClockStyle.NO_LEADING_ZERO
        ),
        PeriodField(id="period", label="Třetina", roi=roi("period")),
        NumberField(id="scoreh", label="Góly domácí", roi=roi("scoreh")),
        NumberField(id="scorea", label="Góly hosté", roi=roi("scorea")),
    ]
    for team, name in (("h", "domácí"), ("a", "hosté")):
        for i in (1, 2):
            fields.append(
                ClockField(
                    id=f"penalty{team}{i}",
                    label=f"Trest {name} {i}",
                    roi=roi(f"penalty{team}{i}"),
                    blank=BlankPolicy.CLEAR,
                )
            )
    return Profile(
        name=video.parent.name,
        source=SourceConfig(
            path=str(video.resolve()),
            loop=False,
            deinterlace=Deinterlace.BLEND if interlaced else Deinterlace.NONE,
        ),
        geometry=GeometryConfig(corners=[tuple(c) for c in cam.corners]),  # type: ignore[misc]
        fields=fields,
    )


def occluder_at(tl: Timeline, tenth: int) -> float | None:
    for iv in tl.intervals:
        if iv.kind == "occlusion" and iv.start <= tenth < iv.end:
            return 0.1 + 0.3 * (tenth - iv.start) / max(1, iv.end - iv.start)
    return None


def render(
    tl: Timeline,
    out: Path,
    fps: int,
    cam_style: CameraStyle,
    led: LedStyle,
    interlaced: bool,
    seed: int,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    board_shape = (ROWS * led.pitch, COLS * led.pitch)
    cam = Camera(cam_style, board_shape, seed)
    w, h = cam_style.frame
    writer = cv2.VideoWriter(str(out / "match.mp4"), cv2.VideoWriter.fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise SystemExit("can't open the video writer (mp4v)")
    cache: dict[tuple[str, ...], np.ndarray] = {}

    def board_at(t_s: float) -> np.ndarray:
        tenth = min(tl.tenths - 1, int(t_s * 10))
        if tl.foreign(tenth):
            return foreign_board(t_s, led)
        state = tl.states[tenth]
        if state.texts not in cache:
            if len(cache) > 64:
                cache.clear()
            cache[state.texts] = led_board(state.as_dict(), led)
        return cache[state.texts]

    frames = int(tl.tenths / 10 * fps)
    last: dict[str, tuple[str, bool]] = {}
    started = time.monotonic()
    with (out / "truth.jsonl").open("w", encoding="utf-8") as truth:
        for i in range(frames):
            t = i / fps
            tenth = min(tl.tenths - 1, int(t * 10))
            occ = occluder_at(tl, tenth)
            frame = cam.shoot(board_at(t), i, occ)
            if interlaced:  # second field 20 ms later
                frame = weave(frame, cam.shoot(board_at(t + 0.5 / fps), i, occ))
            writer.write(frame)
            hidden = tl.hidden(tenth)
            if occ is not None:
                hidden |= cam.covered_boxes(occ, BOXES, led.pitch, CROP_MARGIN)
            for name, value in tl.states[tenth].as_dict().items():
                state = (value, name not in hidden)
                if last.get(name) != state:
                    last[name] = state
                    truth.write(
                        json.dumps(
                            {
                                "frame": i,
                                "t": round(t, 3),
                                "field": name,
                                "value": value,
                                "visible": state[1],
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            if i % (fps * 20) == 0:
                print(f"  {t:6.1f} s / {frames / fps:.0f} s  ({time.monotonic() - started:.0f} s)")
    writer.release()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--short", action="store_true", help="~25 s scenario (tests)")
    parser.add_argument("--hard", action="store_true", help="smaller, darker, blurrier board")
    parser.add_argument("--interlaced", action="store_true", help="woven fields like 1080i")
    parser.add_argument("--no-tenths", action="store_true")
    parser.add_argument(
        "--font",
        choices=["sans", "seg7", "dot"],
        default="sans",
        help="how values are drawn: video wall sans, 7-segment, 5x7 dot matrix",
    )
    parser.add_argument("--direction", choices=["down", "up"], default="down")
    args = parser.parse_args()

    tl = simulate(args.seed, not args.no_tenths, args.direction, args.short)
    cam = HARD if args.hard else CameraStyle()
    print(f"rendering {tl.tenths / 10:.0f} s at {args.fps} fps -> {args.out}")
    render(tl, args.out, args.fps, cam, LedStyle(font=args.font), args.interlaced, args.seed)
    save_profile(
        make_profile(cam, args.out / "match.mp4", args.interlaced), args.out / "profile.json"
    )
    add_anchors(args.out)  # captions as layout-guard anchors, from the first frame
    meta = vars(args) | {"out": str(args.out), "fields": FIELDS, "seconds": tl.tenths / 10}
    (args.out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
