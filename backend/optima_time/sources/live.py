"""Base for live sources (NDI, capture devices): a grab thread that keeps only the newest frame
and reconnects after a failure with a growing delay (SPEC 8).

Subclasses implement _connect() (open, may raise), _grab() (the next frame, or None when there
was none for a while; raise when the connection is broken) and _disconnect().
"""

from __future__ import annotations

import logging
import threading
import time
from abc import abstractmethod

import numpy as np
import numpy.typing as npt

from optima_time.config.models import Deinterlace
from optima_time.preprocess import deinterlace
from optima_time.sources.base import Frame, SourceState, VideoSource

log = logging.getLogger(__name__)

BACKOFF_S = (0.5, 1.0, 2.0, 4.0, 8.0)  # then stays at the last value
NO_FRAME_LOST_S = 3.0  # connected but no frame for this long: lost, reconnect


class SourceUnavailable(RuntimeError):
    """The platform or a library this source needs is missing (e.g. NDI on a machine
    without cyndilib, DirectShow off Windows)."""


class LiveSource(VideoSource):
    name = "live"

    def __init__(self, deinterlace_mode: Deinterlace = Deinterlace.NONE) -> None:
        super().__init__()
        self.deinterlace_mode = deinterlace_mode
        self._cond = threading.Condition()
        self._latest: Frame | None = None
        self._latest_read = True
        self._seq = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.reconnects = 0

    # --- for subclasses

    @abstractmethod
    def _connect(self) -> None: ...

    @abstractmethod
    def _grab(self) -> npt.NDArray[np.uint8] | None: ...

    @abstractmethod
    def _disconnect(self) -> None: ...

    # --- VideoSource

    def open(self) -> None:
        self._stop.clear()
        self.state = SourceState.CONNECTING
        self._thread = threading.Thread(target=self._run, name=f"source-{self.name}", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    def read_latest(self, timeout: float = 1.0) -> Frame | None:
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._latest_read:
                left = deadline - time.monotonic()
                if left <= 0 or self._stop.is_set():
                    return None
                self._cond.wait(left)
            self._latest_read = True
            return self._latest

    # --- grab thread

    def _run(self) -> None:
        attempt = 0
        while not self._stop.is_set():
            try:
                self.state = SourceState.CONNECTING
                self._connect()
            except SourceUnavailable as error:
                self.state, self.error = SourceState.LOST, str(error)
                log.error("%s: %s", self.name, error)
                return  # no point retrying
            except Exception as error:
                self._failed(f"connect: {error}", attempt)
                attempt += 1
                continue
            attempt = 0
            self.error = None
            last_frame = time.monotonic()
            try:
                while not self._stop.is_set():
                    image = self._grab()
                    now = time.monotonic()
                    if image is None:
                        if now - last_frame > NO_FRAME_LOST_S:
                            raise TimeoutError(f"no frame for {NO_FRAME_LOST_S:.0f} s")
                        continue
                    last_frame = now
                    self.state = SourceState.OK
                    self._deliver(image)
            except Exception as error:
                self._failed(str(error), attempt)
                attempt += 1
            finally:
                try:
                    self._disconnect()
                except Exception:
                    log.exception("%s: disconnect failed", self.name)

    def _failed(self, message: str, attempt: int) -> None:
        self.state, self.error = SourceState.LOST, message
        self.reconnects += 1
        delay = BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)]
        log.warning("%s: %s; reconnecting in %.1f s", self.name, message, delay)
        self._stop.wait(delay)

    def _deliver(self, image: npt.NDArray[np.uint8]) -> None:
        image = deinterlace(image, self.deinterlace_mode)
        h, w = image.shape[:2]
        self.info.width, self.info.height = w, h
        with self.stats.lock:
            self.stats.received += 1
        with self._cond:
            if not self._latest_read:
                with self.stats.lock:
                    self.stats.dropped += 1
            self._seq += 1
            self._latest = Frame(image, self._seq, time.monotonic_ns())
            self._latest_read = False
            self._cond.notify_all()
