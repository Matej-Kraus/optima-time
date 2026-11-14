"""Video source interface (SPEC 8). Platform sources live behind it and report themselves
unavailable elsewhere."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self

import numpy as np
import numpy.typing as npt


class SourceState(StrEnum):
    CONNECTING = "connecting"
    OK = "ok"
    LOST = "lost"
    ENDED = "ended"  # a file without looping reached its end


@dataclass(frozen=True)
class Frame:
    image: npt.NDArray[np.uint8]  # BGR
    seq: int  # source frame number (1, 2, ...)
    t_ns: int  # time.monotonic_ns() when the frame arrived
    pts: float | None = None  # media time in seconds (files)


@dataclass
class SourceInfo:
    width: int = 0
    height: int = 0
    fps: float = 0.0


@dataclass
class SourceStats:
    received: int = 0
    dropped: int = 0  # replaced before anyone read them ("latest wins")
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)


class VideoSource(ABC):
    def __init__(self) -> None:
        self.state = SourceState.CONNECTING
        self.info = SourceInfo()
        self.stats = SourceStats()
        self.error: str | None = None

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read_latest(self, timeout: float = 1.0) -> Frame | None:
        """The newest frame not returned yet, waiting up to `timeout` s; None if none came."""

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
