"""Video file or image as a source, for development, tests and evaluation (SPEC 8).

speed > 0: a background thread decodes at `speed` x real time and keeps only the newest frame
           (like a live source: a slow reader misses frames, counted as dropped).
speed == 0: as fast as possible: every read decodes the next frame, nothing is dropped
           (for tools/eval).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from optima_time.config.models import Deinterlace
from optima_time.imageio import read_image
from optima_time.preprocess import deinterlace
from optima_time.sources.base import Frame, SourceState, VideoSource

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
IMAGE_FPS = 25.0


class FileSource(VideoSource):
    def __init__(
        self,
        path: str | Path,
        loop: bool = True,
        speed: float = 1.0,
        deinterlace_mode: Deinterlace = Deinterlace.NONE,
    ) -> None:
        super().__init__()
        self.path = Path(path)
        self.loop = loop
        self.speed = speed
        self.deinterlace_mode = deinterlace_mode
        self.is_image = self.path.suffix.lower() in IMAGE_SUFFIXES
        self._cap: cv2.VideoCapture | None = None
        self._image: npt.NDArray[np.uint8] | None = None
        self._index = 0  # next frame index in the file
        self._seq = 0
        self._cond = threading.Condition()
        self._latest: Frame | None = None
        self._latest_read = True
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._seek_to: float | None = None

    # --- lifecycle

    def open(self) -> None:
        if not self.path.exists():
            self.state, self.error = SourceState.LOST, f"file not found: {self.path}"
            raise FileNotFoundError(self.path)
        if self.is_image:
            image = read_image(self.path)
            if image is None:
                raise ValueError(f"can't read image {self.path}")
            self._image = image
            h, w = self._image.shape[:2]
            self.info.width, self.info.height, self.info.fps = w, h, IMAGE_FPS
        else:
            cap = cv2.VideoCapture(str(self.path))
            if not cap.isOpened():
                raise ValueError(f"can't open video {self.path}")
            self._cap = cap
            self.info.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.info.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.info.fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        self.state = SourceState.OK
        if self.speed > 0:
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="source-file", daemon=True)
            self._thread.start()

    def close(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def seek(self, seconds: float) -> None:
        """Jump to a media time (applied before the next decoded frame)."""
        with self._cond:
            self._seek_to = max(0.0, seconds)

    # --- decoding

    def _apply_seek(self) -> None:
        with self._cond:
            target, self._seek_to = self._seek_to, None
        if target is None:
            return
        self._index = int(target * self.info.fps)
        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, self._index)
        if self.state is SourceState.ENDED:
            self.state = SourceState.OK

    def _decode_next(self) -> Frame | None:
        """Decode the next frame; None at the end of a file without looping."""
        self._apply_seek()
        if self._image is not None:
            image = self._image
        else:
            assert self._cap is not None
            ok, image = self._cap.read()
            if not ok:
                if not self.loop:
                    self.state = SourceState.ENDED
                    return None
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._index = 0
                ok, image = self._cap.read()
                if not ok:
                    self.state, self.error = SourceState.LOST, "can't decode video"
                    return None
            image = np.asarray(image, np.uint8)
        pts = self._index / self.info.fps
        self._index += 1
        self._seq += 1
        image = deinterlace(image, self.deinterlace_mode)
        with self.stats.lock:
            self.stats.received += 1
        return Frame(image, self._seq, time.monotonic_ns(), pts)

    def _run(self) -> None:
        period = 1.0 / (self.info.fps * self.speed)
        next_at = time.monotonic()
        while not self._stop.is_set():
            frame = self._decode_next()
            if frame is None:
                with self._cond:
                    self._cond.notify_all()
                if self.state is SourceState.ENDED and self._seek_to is None:
                    self._stop.wait(0.05)
                    continue
                self._stop.wait(0.2)
                continue
            with self._cond:
                if not self._latest_read:
                    with self.stats.lock:
                        self.stats.dropped += 1
                self._latest, self._latest_read = frame, False
                self._cond.notify_all()
            next_at += period
            delay = next_at - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            else:
                next_at = time.monotonic()  # fell behind: don't try to catch up

    def read_latest(self, timeout: float = 1.0) -> Frame | None:
        if self.speed == 0:
            if self.state is SourceState.ENDED and self._seek_to is None:
                return None
            return self._decode_next()
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._latest_read:
                left = deadline - time.monotonic()
                if left <= 0 or self._stop.is_set() or self.state is SourceState.ENDED:
                    return None
                self._cond.wait(left)
            self._latest_read = True
            return self._latest
