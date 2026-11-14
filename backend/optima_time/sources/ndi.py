"""NDI source via cyndilib (SPEC 8). The usual way to get the scoreboard camera out of vMix,
which holds the capture card: vMix sends the input (KOM BOX) over NDI.

- Full bandwidth, BGRX/BGRA frames.
- allow_video_fields=False: the NDI SDK then delivers whole frames, never single fields (cyndilib
  defaults to True; with an interlaced source that would mean 1920x540 fields). Combing in a
  woven frame is removed by the profile's deinterlace setting.
- A change of resolution while running is fine: every frame carries its own size.
- The source disappearing: no frames -> LOST -> reconnect with a growing delay (live.py).
"""

from __future__ import annotations

import threading
import time
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from optima_time.config.models import Deinterlace
from optima_time.sources.live import LiveSource, SourceUnavailable

_finder: Any = None
_finder_lock = threading.Lock()
_finder_started = 0.0
DISCOVERY_WARMUP_S = 3.0


def _cyndilib() -> Any:
    try:
        import cyndilib  # noqa: F401
        from cyndilib import finder, receiver, video_frame
        from cyndilib.wrapper import ndi_recv, ndi_structs

        return {
            "Finder": finder.Finder,
            "Receiver": receiver.Receiver,
            "ReceiveFrameType": receiver.ReceiveFrameType,
            "VideoRecvFrame": video_frame.VideoRecvFrame,
            "RecvBandwidth": ndi_recv.RecvBandwidth,
            "RecvColorFormat": ndi_recv.RecvColorFormat,
            "FourCC": ndi_structs.FourCC,
        }
    except ImportError as error:
        raise SourceUnavailable(f"NDI není k dispozici (cyndilib): {error}") from error


def _get_finder() -> Any:
    """One NDI finder for the process: discovery takes a moment, so it stays running."""
    global _finder, _finder_started
    with _finder_lock:
        if _finder is None:
            lib = _cyndilib()
            _finder = lib["Finder"]()
            _finder.open()
            _finder_started = time.monotonic()
        return _finder


def list_ndi_sources(wait_s: float = 1.0) -> list[str]:
    """NDI source names seen on the network. Right after start, discovery may need a moment."""
    finder = _get_finder()
    names = list(finder.update_sources())
    warmup_left = DISCOVERY_WARMUP_S - (time.monotonic() - _finder_started)
    if not names and warmup_left > 0 and wait_s > 0:
        finder.wait_for_sources(min(wait_s, warmup_left))
        names = list(finder.update_sources())
    return names


class NdiSource(LiveSource):
    name = "ndi"

    def __init__(self, source_name: str, deinterlace_mode: Deinterlace = Deinterlace.NONE):
        super().__init__(deinterlace_mode)
        self.source_name = source_name
        self._lib: Any = None
        self._receiver: Any = None
        self._frame: Any = None

    def _connect(self) -> None:
        lib = self._lib = _cyndilib()
        finder = _get_finder()
        names = list_ndi_sources(wait_s=2.0)
        if self.source_name not in names:
            raise ConnectionError(f"zdroj NDI {self.source_name!r} není v síti (vidím: {names})")
        receiver = lib["Receiver"](
            color_format=lib["RecvColorFormat"].BGRX_BGRA,
            bandwidth=lib["RecvBandwidth"].highest,
            allow_video_fields=False,
        )
        frame = lib["VideoRecvFrame"]()
        receiver.set_video_frame(frame)
        receiver.set_source(finder.get_source(self.source_name))
        deadline = time.monotonic() + 5
        while not receiver.is_connected():
            if time.monotonic() > deadline or self._stop.is_set():
                raise ConnectionError("NDI connection timed out")
            receiver.receive(lib["ReceiveFrameType"].recv_all, 100)
        self._receiver, self._frame = receiver, frame

    def _grab(self) -> npt.NDArray[np.uint8] | None:
        lib, receiver, frame = self._lib, self._receiver, self._frame
        if not receiver.is_connected():
            raise ConnectionError("NDI disconnected")
        ret = receiver.receive(lib["ReceiveFrameType"].recv_video, 500)
        if ret != lib["ReceiveFrameType"].recv_video or min(frame.xres, frame.yres) == 0:
            return None
        buf = np.empty(frame.get_buffer_size(), dtype=np.uint8)
        frame.fill_p_data(buf)
        rate = frame.get_frame_rate()
        if rate:
            self.info.fps = float(rate)
        image = buf.reshape(frame.yres, frame.xres, 4)
        return np.asarray(cv2.cvtColor(image, cv2.COLOR_BGRA2BGR), np.uint8)

    def _disconnect(self) -> None:
        if self._receiver is not None:
            self._receiver.disconnect()
        self._receiver = self._frame = None
