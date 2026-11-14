"""Runs source -> pipeline in a background thread and keeps the latest results for the API.

Milestone 1: one file source, no outputs, no supervisor yet (Milestones 2-3).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from optima_time.config.models import Profile
from optima_time.config.store import save_profile
from optima_time.pipeline import FrameResult, Pipeline
from optima_time.sources.base import Frame, SourceState, VideoSource
from optima_time.sources.file import FileSource

log = logging.getLogger(__name__)


@dataclass
class Snapshot:
    frame: Frame | None
    rectified: npt.NDArray[np.uint8] | None
    result: FrameResult | None
    processing_fps: float


def make_source(profile: Profile) -> VideoSource | None:
    cfg = profile.source
    if not cfg.path:
        return None
    return FileSource(cfg.path, cfg.loop, cfg.speed, cfg.deinterlace)


class Runner:
    def __init__(self, profile: Profile, profile_path: Path | None, threads: int = 2) -> None:
        self.profile_path = profile_path
        self._profile = profile
        self.pipeline = Pipeline(profile, threads=threads, keep_crops=True)
        self._lock = threading.Lock()
        self._source: VideoSource | None = None
        self._frame: Frame | None = None
        self._result: FrameResult | None = None
        self._done_times: deque[float] = deque(maxlen=50)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None

    # --- profile

    @property
    def profile(self) -> Profile:
        with self._lock:
            return self._profile

    def update_profile(self, profile: Profile, save: bool = True) -> None:
        with self._lock:
            old = self._profile
            self._profile = profile
        self.pipeline.update_profile(profile)
        if save and self.profile_path is not None:
            save_profile(profile, self.profile_path)
        if profile.source != old.source:
            self._restart_source()

    # --- lifecycle

    def start(self) -> None:
        self._open_source()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pipeline", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        with self._lock:
            source, self._source = self._source, None
        if source is not None:
            source.close()

    def _open_source(self) -> None:
        source = make_source(self.profile)
        if source is not None:
            try:
                source.open()
                self.error = None
            except (OSError, ValueError) as error:
                self.error = f"Zdroj nejde otevřít: {error}"
                log.error("%s", self.error)
                source = None
        with self._lock:
            self._source = source

    def _restart_source(self) -> None:
        with self._lock:
            source, self._source = self._source, None
        if source is not None:
            source.close()
        self._open_source()

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                source = self._source
            if source is None or source.state is SourceState.ENDED:
                self._stop.wait(0.2)
                continue
            frame = source.read_latest(timeout=0.5)
            if frame is None:
                continue
            try:
                result = self.pipeline.process(frame)
            except Exception:  # never let a bad frame kill the thread
                log.exception("pipeline failed on frame %s", frame.seq)
                self._stop.wait(0.1)
                continue
            with self._lock:
                self._frame, self._result = frame, result
                self._done_times.append(time.monotonic())

    # --- for the API

    def snapshot(self) -> Snapshot:
        with self._lock:
            times = list(self._done_times)
            fps = (
                (len(times) - 1) / (times[-1] - times[0])
                if len(times) > 1 and times[-1] > times[0]
                else 0.0
            )
            return Snapshot(self._frame, self.pipeline.last_rectified, self._result, fps)

    def source_status(self) -> dict:
        with self._lock:
            source = self._source
        if source is None:
            return {"state": "none", "error": self.error}
        return {
            "state": source.state.value,
            "width": source.info.width,
            "height": source.info.height,
            "fps": source.info.fps,
            "received": source.stats.received,
            "dropped": source.stats.dropped,
            "error": source.error or self.error,
        }
