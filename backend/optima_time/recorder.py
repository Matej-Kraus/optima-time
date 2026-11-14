"""Record a sample from the live source for testing and tuning (SPEC 13.3 "Nahrát vzorek").

Writes N seconds of the rectified board to <samples>/<time>/:
  match.mp4       the rectified board, every frame the pipeline processed
  readings.jsonl  per frame: every field's status, raw OCR text, confidence and published text
  profile.json    the profile, with the source pointing at match.mp4 and corners covering the
                  whole image (the video is already rectified), ready for tools/eval and
                  tools/labeler

Frames go through a bounded queue to a writer thread, so recording never slows the pipeline;
if the disk can't keep up, frames are dropped and counted.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from optima_time.config.models import GeometryConfig, Profile, SourceConfig
from optima_time.config.store import app_dir, save_profile
from optima_time.pipeline import FrameResult

log = logging.getLogger(__name__)

QUEUE_SIZE = 100


def samples_dir() -> Path:
    return app_dir() / "samples"


@dataclass
class RecorderStatus:
    active: bool = False
    folder: str = ""
    seconds: float = 0
    frames: int = 0
    dropped: int = 0
    error: str | None = None
    started_wall: float | None = None


@dataclass
class _Item:
    rectified: npt.NDArray[np.uint8]
    result: FrameResult
    values: dict[str, str] = field(default_factory=dict)


class SampleRecorder:
    def __init__(self) -> None:
        self.status = RecorderStatus()
        self._queue: queue.Queue[_Item | None] = queue.Queue(QUEUE_SIZE)
        self._thread: threading.Thread | None = None
        self._until = 0.0
        self._lock = threading.Lock()

    def start(self, profile: Profile, seconds: float, root: Path | None = None) -> Path:
        with self._lock:
            if self.status.active:
                raise RuntimeError("nahrávání už běží")
            folder = (root or samples_dir()) / time.strftime("%Y%m%d-%H%M%S")
            folder.mkdir(parents=True, exist_ok=True)
            self.status = RecorderStatus(True, str(folder), seconds, started_wall=time.time())
            self._until = time.monotonic() + seconds
            self._queue = queue.Queue(QUEUE_SIZE)
            self._thread = threading.Thread(
                target=self._run, args=(profile, folder), name="recorder", daemon=True
            )
            self._thread.start()
            return folder

    def offer(
        self, rectified: npt.NDArray[np.uint8] | None, result: FrameResult, values: dict[str, str]
    ) -> None:
        """Called by the pipeline thread for every processed frame; never blocks."""
        if not self.status.active or rectified is None:
            return
        if time.monotonic() >= self._until:
            self._stop_feeding()
            return
        try:
            self._queue.put_nowait(_Item(rectified, result, values))
        except queue.Full:
            self.status.dropped += 1

    def _stop_feeding(self) -> None:
        with self._lock:
            if self.status.active:
                self.status.active = False
                self._queue.put(None)

    def stop(self) -> None:
        self._stop_feeding()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self, profile: Profile, folder: Path) -> None:
        writer: cv2.VideoWriter | None = None
        size: tuple[int, int] | None = None
        fps = 25.0
        try:
            with (folder / "readings.jsonl").open("w", encoding="utf-8") as readings:
                while True:
                    item = self._queue.get()
                    if item is None:
                        break
                    h, w = item.rectified.shape[:2]
                    if writer is None:
                        size = (w, h)
                        writer = cv2.VideoWriter(
                            str(folder / "match.mp4"), cv2.VideoWriter.fourcc(*"mp4v"), fps, size
                        )
                        if not writer.isOpened():
                            raise OSError("can't open the video writer")
                    if (w, h) != size:  # the geometry changed while recording
                        raise ValueError("rozměr narovnaného obrazu se změnil, nahrávání končí")
                    writer.write(item.rectified)
                    r = item.result
                    readings.write(
                        json.dumps(
                            {
                                "frame": self.status.frames,
                                "source_seq": r.seq,
                                "fields": {
                                    fid: {
                                        "status": x.status.value,
                                        "raw": x.reading.text if x.reading else None,
                                        "conf": round(x.reading.confidence, 3)
                                        if x.reading
                                        else None,
                                        "cached": x.cached,
                                    }
                                    for fid, x in r.fields.items()
                                },
                                "guard": r.guard.state.value,
                                "published": item.values,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    self.status.frames += 1
            sample = profile.model_copy(deep=True)
            sample.name = f"vzorek-{folder.name}"
            sample.source = SourceConfig(path=str((folder / "match.mp4").resolve()), loop=False)
            sample.geometry = GeometryConfig(
                corners=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
                max_width=max(size or (64, 64)),
            )
            save_profile(sample, folder / "profile.json")
        except Exception as error:
            self.status.error = str(error)
            log.exception("sample recording failed")
        finally:
            if writer is not None:
                writer.release()
            self.status.active = False
