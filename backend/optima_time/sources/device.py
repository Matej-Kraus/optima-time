"""Capture devices through OpenCV (SPEC 8): capture cards, USB grabbers, webcams and vMix's
virtual cameras ("vMix Video", "vMix Video External 2").

Devices are listed with names via cv2-enumerate-cameras; its index already encodes the OpenCV
backend (e.g. 700+ = DirectShow, 1400+ = Media Foundation on Windows), so cv2.VideoCapture(index)
opens exactly that device. Indices can shift when devices come and go, so the profile also
stores the name and the source looks the index up by name when it (re)connects.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import cv2
import numpy as np
import numpy.typing as npt

from optima_time.config.models import Deinterlace
from optima_time.sources.live import LiveSource

log = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    index: int  # OpenCV index including the backend offset
    name: str
    backend: str

    def as_dict(self) -> dict:
        return asdict(self)


def list_devices() -> list[DeviceInfo]:
    try:
        from cv2_enumerate_cameras import enumerate_cameras
    except ImportError:
        return []
    out = []
    try:
        for cam in enumerate_cameras():
            backend_id = cam.backend or (int(cam.index) // 100 * 100)  # index = backend + n
            try:
                backend = cv2.videoio_registry.getBackendName(backend_id)
            except cv2.error:
                backend = "?"
            out.append(DeviceInfo(int(cam.index), str(cam.name).strip(), str(backend)))
    except Exception as error:  # enumeration must never break the app
        log.warning("device enumeration failed: %s", error)
    return out


class DeviceSource(LiveSource):
    name = "device"

    def __init__(
        self,
        index: int,
        device_name: str = "",
        width: int = 0,
        height: int = 0,
        fps: float = 0.0,
        fourcc: str = "",
        deinterlace_mode: Deinterlace = Deinterlace.NONE,
    ) -> None:
        super().__init__(deinterlace_mode)
        self.index, self.device_name = index, device_name
        self.want = (width, height, fps, fourcc)
        self._cap: cv2.VideoCapture | None = None

    def _resolve_index(self) -> int:
        """The device's current index, found by name when the name is known."""
        if not self.device_name:
            return self.index
        for d in list_devices():
            if d.name == self.device_name:
                return d.index
        raise ConnectionError(f"zařízení {self.device_name!r} není připojené")

    def _connect(self) -> None:
        index = self._resolve_index()
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            raise ConnectionError(
                f"zařízení {index} nejde otevřít (nemá ho otevřené jiný program?)"
            )
        width, height, fps, fourcc = self.want
        if fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*fourcc[:4].ljust(4)))
        if width and height:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if fps:
            cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # low latency where the backend supports it
        self.info.fps = float(cap.get(cv2.CAP_PROP_FPS)) or fps or 25.0
        self._cap = cap

    def _grab(self) -> npt.NDArray[np.uint8] | None:
        assert self._cap is not None
        ok, image = self._cap.read()
        if not ok or image is None:
            raise ConnectionError("zařízení přestalo posílat obraz")
        return np.asarray(image, np.uint8)

    def _disconnect(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
