"""Profile: settings for one hall and sport (SPEC 2, 14.1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from optima_time.fields.models import FieldConfig, Model, Roi, check_unique_ids

SCHEMA_VERSION = 1


class Deinterlace(StrEnum):
    NONE = "none"
    BLEND = "blend"  # average neighbouring lines: steady, slightly soft
    BOB = "bob"  # keep one field, stretch it: sharp, half vertical resolution


class SourceConfig(Model):
    type: Literal["file", "ndi", "device"] = "file"
    # file / image
    path: str = ""
    loop: bool = True
    speed: float = Field(default=1.0, ge=0)  # 1 = real time, 0 = as fast as possible
    # NDI
    ndi_name: str = ""  # e.g. "PC (vMix - KOM BOX)"
    # capture device (OpenCV index incl. backend offset; the name finds it again if it moves)
    device_index: int = Field(default=-1, ge=-1)
    device_name: str = ""
    width: int = Field(default=0, ge=0, le=7680)  # 0 = device default
    height: int = Field(default=0, ge=0, le=4320)
    fps: float = Field(default=0.0, ge=0, le=240)
    fourcc: str = Field(default="", max_length=4)  # e.g. "MJPG"
    deinterlace: Deinterlace = Deinterlace.NONE


class GeometryConfig(Model):
    # Board corners relative to the source frame (0-1): top-left, top-right, bottom-right,
    # bottom-left as seen on the board.
    corners: list[tuple[float, float]] = Field(
        default=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)], min_length=4, max_length=4
    )
    rotate: Literal[0, 90, 180, 270] = 0
    max_width: int = Field(default=1280, ge=64, le=4096)

    @model_validator(mode="after")
    def _relative(self) -> GeometryConfig:
        for x, y in self.corners:
            if not (-0.5 <= x <= 1.5 and -0.5 <= y <= 1.5):
                raise ValueError("corners must be relative coordinates (0-1)")
        return self


class AnchorConfig(Model):
    roi: Roi  # relative to the rectified board
    template: str = ""  # base64 PNG captured from a frame (guard.capture_template)


class GuardConfig(Model):
    anchors: list[AnchorConfig] = Field(default_factory=list, max_length=3)
    threshold: float = Field(default=0.8, ge=0, le=1)  # normalized correlation (DECISIONS D17)
    recover_frames: int = Field(default=5, ge=1, le=250)
    search_margin: float = Field(default=0.3, ge=0, le=2)  # x anchor height, for vibration


class NewLine(StrEnum):
    CRLF = "crlf"
    LF = "lf"


class XmlFileOutput(Model):
    enabled: bool = True
    path: str = ""
    newline: NewLine = NewLine.CRLF
    clear_on_exit: bool = False  # else the last values stay in the file


class OutputsConfig(Model):
    xml_file: XmlFileOutput = XmlFileOutput()


class BlendMode(StrEnum):
    MAX = "max"  # keeps LEDs lit when the camera catches them dark (PWM flicker)
    MEAN = "mean"  # smooths noise and moiré


class PreprocessConfig(Model):
    """Optional blending of the last N frames against LED flicker and moiré (SPEC 9.2).
    Off by default: it delays changes by up to N-1 frames."""

    blend_frames: int = Field(default=1, ge=1, le=5)  # 1 = off
    blend_mode: BlendMode = BlendMode.MAX


class DetectionConfig(Model):
    """Read a field only when its crop changed (SPEC 10.5)."""

    enabled: bool = True
    threshold: float = Field(default=0.15, ge=0, le=5)  # preprocess.difference (D22)
    max_age_ms: int = Field(default=1000, ge=100, le=10_000)  # read at least this often


class Profile(Model):
    schema_version: Literal[1] = SCHEMA_VERSION
    name: str = "profil"
    source: SourceConfig = SourceConfig()
    geometry: GeometryConfig = GeometryConfig()
    fields: list[FieldConfig] = Field(default_factory=list)
    preprocess: PreprocessConfig = PreprocessConfig()
    guard: GuardConfig = GuardConfig()
    detection: DetectionConfig = DetectionConfig()
    outputs: OutputsConfig = OutputsConfig()

    @model_validator(mode="after")
    def _unique(self) -> Profile:
        check_unique_ids(self.fields)
        return self
