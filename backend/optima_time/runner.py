"""Runs source -> pipeline -> board state -> outputs, and keeps the latest results for the API.

Threads (SPEC 7.2): this runner's pipeline thread, one thread per output (outputs/base.py), the
source's own thread, and the API's event loop. Between them only the latest data is kept.
"""

from __future__ import annotations

import itertools
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import psutil

from optima_time.config.models import NewLine, Profile
from optima_time.config.store import save_profile
from optima_time.guard import history_frame
from optima_time.outputs.base import OutputHub, OutputWorker
from optima_time.outputs.vmix_api import VmixApiWorker
from optima_time.outputs.xml_file import XmlFileWorker
from optima_time.pipeline import FrameResult, Pipeline
from optima_time.recorder import SampleRecorder
from optima_time.sources.base import Frame, SourceState, VideoSource
from optima_time.sources.device import DeviceSource
from optima_time.sources.file import FileSource
from optima_time.sources.ndi import NdiSource
from optima_time.sources.stream import StreamSource
from optima_time.state import BoardState
from optima_time.supervisor import Supervisor

log = logging.getLogger(__name__)

SOURCE_LOST_AFTER_S = 1.5  # no frame for this long: fields go stale


@dataclass
class Snapshot:
    frame: Frame | None
    rectified: npt.NDArray[np.uint8] | None
    result: FrameResult | None
    processing_fps: float


def make_source(profile: Profile) -> VideoSource | None:
    cfg = profile.source
    if cfg.type == "ndi":
        return NdiSource(cfg.ndi_name, cfg.deinterlace) if cfg.ndi_name else None
    if cfg.type == "device":
        if cfg.device_index < 0 and not cfg.device_name:
            return None
        return DeviceSource(
            cfg.device_index,
            cfg.device_name,
            cfg.width,
            cfg.height,
            cfg.fps,
            cfg.fourcc,
            cfg.deinterlace,
        )
    if cfg.type == "stream":
        return StreamSource(cfg.url, cfg.deinterlace) if cfg.url.strip() else None
    if not cfg.path:
        return None
    return FileSource(cfg.path, cfg.loop, cfg.speed, cfg.deinterlace)


def make_workers(profile: Profile) -> list[OutputWorker]:
    workers: list[OutputWorker] = []
    xml = profile.outputs.xml_file
    if xml.enabled and xml.path:
        newline = "\r\n" if xml.newline is NewLine.CRLF else "\n"
        workers.append(XmlFileWorker(xml.path, newline))
    api = profile.outputs.vmix_api
    if api.enabled and api.input.strip():
        workers.append(
            VmixApiWorker(api.host.strip(), api.port, api.input.strip(), api.suffix, api.names)
        )
    return workers


class Runner:
    def __init__(
        self,
        profile: Profile,
        profile_path: Path | None,
        threads: int = 2,
        log_dir: Path | None = None,
        log_name: str = "events",
    ) -> None:
        self.profile_path = profile_path
        self._profile = profile
        self.pipeline = Pipeline(profile, threads=threads, keep_crops=True)
        self._lock = threading.Lock()
        self.hub = OutputHub(make_workers(profile), profile.outputs.delay_ms / 1000)
        initial: dict[str, str] = {}
        for w in self.hub.workers:
            if isinstance(w, XmlFileWorker):
                initial = w.read_existing()
        self.state = BoardState(profile, self.hub, log_dir, initial, log_name)
        self._source: VideoSource | None = None
        self._frame: Frame | None = None
        self._result: FrameResult | None = None
        self._last_frame_at = time.monotonic()
        self._done_times: deque[float] = deque(maxlen=50)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None
        self.heartbeat = time.monotonic()  # the pipeline thread's pulse (supervisor.py)
        self.supervisor = Supervisor(self)
        self.recorder = SampleRecorder()
        self.settings_locked = False  # during a match: the setup can't be changed (SPEC 13.1)
        self.last_test_wall: float | None = None  # when test values last went to vMix
        # telemetry for the diagnostics screen
        self._arrivals: deque[int] = deque(maxlen=100)  # frame arrival times (ns)
        self._frame_ms: deque[float] = deque(maxlen=250)  # pipeline time per frame
        self.guard_history: deque[tuple[float, float | None, str]] = deque(maxlen=240)
        self._guard_at = 0.0
        # small gray copies of the last ~12 s of rectified frames, for anchor suggestions
        self.history: deque[npt.NDArray[np.uint8]] = deque(maxlen=60)
        self._history_at = 0.0
        self.log_dir = log_dir
        self._process = psutil.Process()
        self._cpu_mark = (self._cpu_seconds(), time.monotonic())
        self._cpu_percent = 0.0

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
        self.state.reconfigure(profile)
        if save and self.profile_path is not None:
            save_profile(profile, self.profile_path)
        if profile.outputs != old.outputs:
            self._restart_outputs(profile)
        if profile.source != old.source:
            self._restart_source()

    def switch_profile(self, profile: Profile, path: Path) -> None:
        """Load another profile file (a different hall)."""
        self.profile_path = path
        self.update_profile(profile, save=False)

    # --- lifecycle

    def start(self) -> None:
        self.hub.start()
        self.state.publish_all()
        self._open_source()
        self._stop.clear()
        self.start_pipeline_thread()
        self.supervisor.start()

    def start_pipeline_thread(self) -> None:
        self.heartbeat = time.monotonic()
        self._thread = threading.Thread(target=self._run, name="pipeline", daemon=True)
        self._thread.start()

    def pipeline_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        self.recorder.stop()
        self.supervisor.stop()
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        with self._lock:
            source, self._source = self._source, None
        if source is not None:
            source.close()
        clear = self.profile.outputs.xml_file.clear_on_exit
        self.hub.stop(dict.fromkeys(self.state.output_values(), "") if clear else None)

    def _restart_outputs(self, profile: Profile) -> None:
        self.hub.stop()
        mode = self.hub.mode
        self.hub.workers = make_workers(profile)
        self.hub.delay_s = profile.outputs.delay_ms / 1000
        self.hub.start()
        self.hub.set_mode(mode)
        self.state.publish_all()

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
            self._last_frame_at = time.monotonic()

    def _restart_source(self) -> None:
        with self._lock:
            source, self._source = self._source, None
        if source is not None:
            source.close()
        self._open_source()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.heartbeat = time.monotonic()
            with self._lock:
                source = self._source
            if source is None or source.state is SourceState.ENDED:
                self._mark_source(False)
                self._stop.wait(0.2)
                continue
            frame = source.read_latest(timeout=0.5)
            if frame is None:
                self._mark_source(time.monotonic() - self._last_frame_at < SOURCE_LOST_AFTER_S)
                continue
            self._last_frame_at = time.monotonic()
            try:
                result = self.pipeline.process(frame, self.state.unsettled())
                self.state.update(result, result.guard, True, frame.t_ns)
            except Exception:  # never let a bad frame kill the thread
                log.exception("pipeline failed on frame %s", frame.seq)
                self._stop.wait(0.1)
                continue
            with self._lock:
                self._frame, self._result = frame, result
                self._done_times.append(time.monotonic())
            self._arrivals.append(frame.t_ns)
            self._frame_ms.append(result.timings_ms.get("total", 0.0))
            if time.monotonic() - self._guard_at >= 0.1:  # 24 s of anchor scores
                self._guard_at = time.monotonic()
                scores = result.guard.scores
                self.guard_history.append(
                    (time.time(), min(scores) if scores else None, result.guard.state.value)
                )
            if (
                time.monotonic() - self._history_at >= 0.2
                and self.pipeline.last_rectified is not None
            ):
                self._history_at = time.monotonic()
                self.history.append(history_frame(self.pipeline.last_rectified))
            if self.recorder.status.active:
                self.recorder.offer(self.pipeline.last_rectified, result, self.state.values())

    def _mark_source(self, ok: bool) -> None:
        if not ok:
            self.state.update(None, None, False)

    # --- for the API

    def recent_history(self) -> list[npt.NDArray[np.uint8]]:
        """The kept frames that match the current geometry (same size as the newest)."""
        frames = list(self.history)
        return [f for f in frames if f.shape == frames[-1].shape] if frames else []

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

    def _cpu_seconds(self) -> float:
        t = self._process.cpu_times()
        return t.user + t.system

    def process_status(self) -> dict:
        """CPU (% of one core, averaged over the last ~2 s or more) and memory of this process."""
        now, cpu = time.monotonic(), self._cpu_seconds()
        mark_cpu, mark_t = self._cpu_mark
        if now - mark_t >= 2.0:
            self._cpu_percent = 100 * (cpu - mark_cpu) / (now - mark_t)
            self._cpu_mark = (cpu, now)
        mem = self._process.memory_info().rss
        arrivals = list(self._arrivals)
        gaps = [(b - a) / 1e6 for a, b in itertools.pairwise(arrivals)]
        jitter = float(np.std(gaps)) if len(gaps) > 2 else None
        ms = sorted(self._frame_ms)
        return {
            "frame_jitter_ms": round(jitter, 2) if jitter is not None else None,
            "frame_ms_p50": round(ms[len(ms) // 2], 1) if ms else None,
            "frame_ms_p95": round(ms[int(0.95 * (len(ms) - 1))], 1) if ms else None,
            "cpu_percent": round(self._cpu_percent, 1),
            "cpu_count": psutil.cpu_count() or 1,
            "rss_mb": round(mem / 2**20, 1),
            "threads": self._process.num_threads(),
            "supervisor_restarts": self.supervisor.restarts,
            "pipeline_stuck": self.supervisor.stuck,
        }

    def outputs_status(self) -> dict:
        return {
            "mode": self.hub.mode.value,
            "workers": {
                w.name: w.status.as_dict()
                | {
                    "target": str(getattr(w, "target", None) or getattr(w, "path", "")),
                    "problems": dict(getattr(w, "problems", {})),
                }
                for w in self.hub.workers
            },
        }
