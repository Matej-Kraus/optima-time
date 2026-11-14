"""Recognizer interface (SPEC 10.1). Adding an engine must not require changes to the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import numpy.typing as npt


@dataclass
class Crop:
    image: npt.NDArray[np.uint8]  # BGR, raw colour (never binarized for PP-OCR)
    allowed: str | None = None  # characters the decoder may output (None: any)
    min_width: int | None = None  # engine-specific input width override


@dataclass
class Reading:
    text: str
    confidence: float  # 0-1, mean probability of the kept characters (0 for empty text)
    per_char_confidence: list[float] = field(default_factory=list)
    engine: str = ""
    elapsed_ms: float = 0.0  # time of the batch this crop was read in


class Recognizer(Protocol):
    name: str

    def read(self, crops: list[Crop]) -> list[Reading]:
        """Read every crop (in one go when possible); one Reading per crop, in order."""
        ...
