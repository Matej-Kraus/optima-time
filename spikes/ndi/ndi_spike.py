"""Spike C: receive the scoreboard camera from vMix over NDI and measure what arrives.

One-off experiment (Milestone 0), not product code. Procedure: docs/MANUAL_TESTS.md, M0-C.

Measures: resolution, frame rate (declared and actual), frame format (progressive / interleaved /
fields), FourCC, gaps between frames, process CPU (% of one core), and an interlace "combing"
score. Saves a few frames as PNG to look at.

Fallback without NDI: --opencv-index N opens a capture device through OpenCV (DirectShow on
Windows), e.g. the vMix virtual camera ("vMix Video" / "vMix Video External 2").

Usage:
  uv run --group ndi python spikes/ndi/ndi_spike.py --list
  uv run --group ndi python spikes/ndi/ndi_spike.py --source "KOM BOX" --seconds 60
  uv run --group ndi python spikes/ndi/ndi_spike.py --source "KOM BOX" --no-fields
  uv run python spikes/ndi/ndi_spike.py --opencv-index 1 --seconds 60
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from pathlib import Path

import cv2
import numpy as np

OUT_DIR = Path(__file__).parent / "out"


def combing_score(bgr: np.ndarray) -> float:
    """Adjacent-line vs two-apart difference: ~0.5 progressive (measured), >1 combed (woven fields).

    Interlaced frames woven from two fields taken 20 ms apart differ line-to-line on motion."""
    gray = bgr.max(axis=2).astype(np.float32)
    d1 = np.abs(gray[1:-1] - gray[:-2]).mean()
    d2 = np.abs(gray[2:] - gray[:-2]).mean()
    return float(d1 / max(d2, 1e-6))


def summarize(intervals_ms: list[float], frames: int, seconds: float, cpu_s: float) -> dict:
    s = sorted(intervals_ms) or [0.0]
    return {
        "frames": frames,
        "seconds": round(seconds, 2),
        "fps_actual": round(frames / seconds, 2) if seconds else 0,
        "interval_ms_median": round(statistics.median(s), 2),
        "interval_ms_p99": round(s[int(0.99 * (len(s) - 1))], 2),
        "interval_ms_max": round(s[-1], 2),
        "process_cpu_percent_of_one_core": round(100 * cpu_s / seconds, 1) if seconds else 0,
    }


def save_frames(tag: str, frames: list[np.ndarray]) -> list[dict]:
    OUT_DIR.mkdir(exist_ok=True)
    info = []
    for i, frame in enumerate(frames):
        path = OUT_DIR / f"{tag}_{i}.png"
        cv2.imwrite(str(path), frame)
        info.append({"file": str(path), "combing": round(combing_score(frame), 3)})
    return info


def run_ndi(args: argparse.Namespace) -> dict:
    from cyndilib.finder import Finder
    from cyndilib.receiver import ReceiveFrameType, Receiver
    from cyndilib.video_frame import VideoRecvFrame
    from cyndilib.wrapper.ndi_recv import RecvBandwidth, RecvColorFormat
    from cyndilib.wrapper.ndi_structs import FourCC, FrameFormat

    finder = Finder()
    finder.open()
    deadline = time.monotonic() + args.discover
    names: list[str] = []
    while time.monotonic() < deadline:
        finder.wait_for_sources(0.5)
        names = list(finder.update_sources())
        if args.source and any(args.source.lower() in n.lower() for n in names):
            break
    print("NDI sources:", *([f"  {n}" for n in names] or ["  (none)"]), sep="\n")
    if args.list:
        finder.close()
        return {"sources": names}
    matches = [n for n in names if args.source and args.source.lower() in n.lower()]
    if not matches:
        finder.close()
        raise SystemExit(f"no NDI source matching {args.source!r}")
    name = matches[0]
    print(f"\nconnecting to {name!r} (allow_video_fields={not args.no_fields})")

    receiver = Receiver(
        color_format=RecvColorFormat.BGRX_BGRA,
        bandwidth=RecvBandwidth.highest,
        allow_video_fields=not args.no_fields,
    )
    video = VideoRecvFrame()
    receiver.set_video_frame(video)
    source = finder.get_source(name)
    receiver.set_source(source)

    t_connect = time.monotonic()
    while not receiver.is_connected() and time.monotonic() - t_connect < 10:
        receiver.receive(ReceiveFrameType.recv_all, 100)
    if not receiver.is_connected():
        raise SystemExit("not connected after 10 s")

    meta: dict = {}
    intervals: list[float] = []
    keep: list[np.ndarray] = []
    formats: dict[str, int] = {}
    frames, last = 0, None
    cpu0, t0 = time.process_time(), time.monotonic()
    while time.monotonic() - t0 < args.seconds:
        ret = receiver.receive(ReceiveFrameType.recv_video, 1000)
        if ret != ReceiveFrameType.recv_video or min(video.xres, video.yres) == 0:
            continue
        now = time.monotonic()
        buf = np.empty(video.get_buffer_size(), dtype=np.uint8)
        video.fill_p_data(buf)
        frame = cv2.cvtColor(buf.reshape(video.yres, video.xres, 4), cv2.COLOR_BGRA2BGR)
        fmt = FrameFormat(video.frame_format).name
        formats[fmt] = formats.get(fmt, 0) + 1
        if not meta:
            meta = {
                "source": name,
                "resolution": [video.xres, video.yres],
                "declared_frame_rate": str(video.get_frame_rate()),
                "fourcc": FourCC(video.get_fourcc()).name,
            }
            print("first frame:", meta, fmt)
        if last is not None:
            intervals.append((now - last) * 1000)
        last = now
        frames += 1
        if frames in (1, 50, 200):
            keep.append(frame)
    stats = summarize(intervals, frames, time.monotonic() - t0, time.process_time() - cpu0)
    receiver.disconnect()
    finder.close()
    tag = "ndi_fields" if not args.no_fields else "ndi_nofields"
    return (
        meta
        | {"frame_formats": formats, "allow_video_fields": not args.no_fields}
        | stats
        | {"saved": save_frames(tag, keep)}
    )


def run_opencv(args: argparse.Namespace) -> dict:
    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    cap = cv2.VideoCapture(args.opencv_index, backend)
    if not cap.isOpened():
        raise SystemExit(f"can't open capture device {args.opencv_index}")
    if args.width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    meta = {
        "device_index": args.opencv_index,
        "backend": cap.getBackendName(),
        "resolution": [
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        ],
        "declared_fps": cap.get(cv2.CAP_PROP_FPS),
    }
    print("device:", meta)
    intervals: list[float] = []
    keep: list[np.ndarray] = []
    frames, last = 0, None
    cpu0, t0 = time.process_time(), time.monotonic()
    while time.monotonic() - t0 < args.seconds:
        ok, frame = cap.read()
        if not ok:
            continue
        now = time.monotonic()
        if last is not None:
            intervals.append((now - last) * 1000)
        last = now
        frames += 1
        if frames in (1, 50, 200):
            keep.append(frame)
    stats = summarize(intervals, frames, time.monotonic() - t0, time.process_time() - cpu0)
    cap.release()
    return meta | stats | {"saved": save_frames(f"opencv{args.opencv_index}", keep)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--list", action="store_true", help="only list NDI sources")
    parser.add_argument("--source", help="part of the NDI source name, e.g. 'KOM BOX'")
    parser.add_argument("--no-fields", action="store_true", help="allow_video_fields=False")
    parser.add_argument("--discover", type=float, default=5.0, help="seconds to look for sources")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--opencv-index", type=int, help="use an OpenCV capture device instead")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    args = parser.parse_args()

    result = run_opencv(args) if args.opencv_index is not None else run_ndi(args)
    result |= {"machine": f"{platform.system()} {platform.release()} {platform.processor()}"}
    print("\n" + json.dumps(result, indent=1, ensure_ascii=False))
    if not args.list:
        OUT_DIR.mkdir(exist_ok=True)
        name = f"report_{int(time.time())}.json"
        (OUT_DIR / name).write_text(
            json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nreport: {OUT_DIR / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
