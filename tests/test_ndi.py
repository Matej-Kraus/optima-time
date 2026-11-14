"""NDI end to end against a local test sender (cyndilib). Skipped when NDI can't run here.

Opt-in (OPTIMA_TIME_NDI_TEST=1): it uses the network and takes a few seconds.
"""

import os
import threading
import time
from fractions import Fraction

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("OPTIMA_TIME_NDI_TEST") != "1", reason="set OPTIMA_TIME_NDI_TEST=1 to run"
)


def test_receives_frames_from_local_sender() -> None:
    from cyndilib.sender import Sender
    from cyndilib.video_frame import VideoSendFrame
    from cyndilib.wrapper.ndi_structs import FourCC

    from optima_time.sources.base import SourceState
    from optima_time.sources.ndi import NdiSource, list_ndi_sources

    name = f"optima-test-{os.getpid()}"
    stop = threading.Event()

    def send() -> None:
        frame = VideoSendFrame()
        frame.set_resolution(640, 360)
        frame.set_frame_rate(Fraction(25, 1))
        frame.set_fourcc(FourCC.BGRA)
        sender = Sender(name)
        sender.set_video_frame(frame)
        with sender:
            n = 0
            while not stop.is_set():
                img = np.zeros((360, 640, 4), np.uint8)
                img[:, :, 1] = n % 256
                sender.write_video(img.ravel())
                n += 1
                time.sleep(0.04)

    t = threading.Thread(target=send, daemon=True)
    t.start()
    try:
        full = None
        for _ in range(40):
            full = next((s for s in list_ndi_sources(0.5) if name in s), None)
            if full:
                break
        assert full, "test sender not discovered"
        src = NdiSource(full)
        src.open()
        try:
            frames = [src.read_latest(5) for _ in range(10)]
            assert all(f is not None for f in frames)
            assert frames[-1] is not None and frames[-1].image.shape == (360, 640, 3)
            assert src.state is SourceState.OK
        finally:
            src.close()
    finally:
        stop.set()
        t.join(2)
