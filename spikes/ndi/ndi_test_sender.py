"""Spike C helper: a local NDI test source (moving clock text), to check ndi_spike.py without vMix.

Usage: uv run --group ndi python spikes/ndi/ndi_test_sender.py --seconds 30
"""

import argparse
import time
from fractions import Fraction

import cv2
import numpy as np
from cyndilib.sender import Sender
from cyndilib.video_frame import VideoSendFrame
from cyndilib.wrapper.ndi_structs import FourCC


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="optima-test")
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--fps", type=int, default=25)
    args = parser.parse_args()

    w, h = 1920, 1080
    frame = VideoSendFrame()
    frame.set_resolution(w, h)
    frame.set_frame_rate(Fraction(args.fps, 1))
    frame.set_fourcc(FourCC.BGRA)
    sender = Sender(args.name)
    sender.set_video_frame(frame)
    with sender:
        t0 = time.monotonic()
        n = 0
        while time.monotonic() - t0 < args.seconds:
            img = np.zeros((h, w, 4), np.uint8)
            secs = 1200 - n // args.fps
            cv2.putText(
                img,
                f"{secs // 60:02d}:{secs % 60:02d}",
                (600 + n % 200, 600),
                cv2.FONT_HERSHEY_SIMPLEX,
                8,
                (40, 255, 40, 255),
                20,
            )
            sender.write_video(img.ravel())
            n += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
