"""Network video streams: SRT, RTSP, RTMP, UDP/RTP (MPEG-TS), HTTP (SPEC 6, phase-2 input).

OpenCV's FFmpeg backend opens the URL. Low-latency options are set per open (no input buffer,
RTSP over TCP so a lossy network doesn't smear the picture), and timeouts make a dead stream
fail instead of hanging. The LiveSource thread keeps only the newest frame, so a backlog never
builds up. Typical URLs:

  srt://192.168.1.20:9000?mode=caller        an SRT sender (e.g. vMix SRT output) as listener
  srt://0.0.0.0:9000?mode=listener           we listen; the sender calls us
  rtsp://user:pass@192.168.1.30:554/stream1  an IP camera
  udp://0.0.0.0:5000                         MPEG-TS over UDP
"""

from __future__ import annotations

import os
import threading

import cv2
import numpy as np
import numpy.typing as npt

from optima_time.config.models import Deinterlace
from optima_time.sources.live import LiveSource

# FFmpeg chatter (e.g. "non-existing PPS" before the first keyframe) is noise in our logs
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")

OPTIONS_ENV = "OPENCV_FFMPEG_CAPTURE_OPTIONS"
_OPTIONS_LOCK = threading.Lock()
LOW_LATENCY = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;500000"
OPEN_TIMEOUT_MS = 8000
READ_TIMEOUT_MS = 3000
SCHEMES = (
    "srt://",
    "rtsp://",
    "rtsps://",
    "rtmp://",
    "rtmps://",
    "udp://",
    "rtp://",
    "http://",
    "https://",
)


def check_url(url: str) -> str:
    """The URL stripped, or ValueError with a Czech message for the UI."""
    url = url.strip()
    if not url.lower().startswith(SCHEMES):
        raise ValueError(
            "adresa streamu musí začínat srt://, rtsp://, rtmp://, udp:// nebo http://"
        )
    return url


def safe_url(url: str) -> str:
    """The URL without a password, for logs and the UI."""
    scheme, sep, rest = url.partition("://")
    if "@" in rest.split("/", 1)[0]:
        rest = "***@" + rest.split("@", 1)[1]
    return scheme + sep + rest


class StreamSource(LiveSource):
    name = "stream"

    def __init__(self, url: str, deinterlace_mode: Deinterlace = Deinterlace.NONE) -> None:
        super().__init__(deinterlace_mode)
        self.url = url.strip()
        self._cap: cv2.VideoCapture | None = None

    def _connect(self) -> None:
        url = check_url(self.url)
        with _OPTIONS_LOCK:  # FFmpeg reads the options from the environment at open time
            previous = os.environ.get(OPTIONS_ENV)
            os.environ[OPTIONS_ENV] = LOW_LATENCY
            try:
                cap = self._open(url)
            finally:
                if previous is None:
                    os.environ.pop(OPTIONS_ENV, None)
                else:
                    os.environ[OPTIONS_ENV] = previous
        if not cap.isOpened():
            cap.release()
            raise ConnectionError(
                f"stream {safe_url(url)} nejde otevřít (běží vysílání, sedí adresa a port?)"
            )
        self.info.fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 25.0
        if not 1 <= self.info.fps <= 240:  # some streams report nonsense (e.g. 90000)
            self.info.fps = 25.0
        self._cap = cap

    @staticmethod
    def _open(url: str) -> cv2.VideoCapture:
        timeouts = [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            OPEN_TIMEOUT_MS,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            READ_TIMEOUT_MS,
        ]
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG, timeouts)

    def _grab(self) -> npt.NDArray[np.uint8] | None:
        assert self._cap is not None
        ok, image = self._cap.read()
        if not ok or image is None:
            raise ConnectionError("stream přestal posílat obraz")
        return np.asarray(image, np.uint8)

    def _disconnect(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
