"""Profile: settings for one hall and sport (SPEC 2, 14.1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from optima_time.fields.models import FieldConfig, Model, check_unique_ids

SCHEMA_VERSION = 1


class Deinterlace(StrEnum):
    NONE = "none"
    BLEND = "blend"  # average neighbouring lines: steady, slightly soft
    BOB = "bob"  # keep one field, stretch it: sharp, half vertical resolution


class SourceConfig(Model):
    type: Literal["file"] = "file"  # ndi, device: Milestone 3
    path: str = ""
    loop: bool = True
    speed: float = Field(default=1.0, ge=0)  # 1 = real time, 0 = as fast as possible
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


class Profile(Model):
    schema_version: Literal[1] = SCHEMA_VERSION
    name: str = "profil"
    source: SourceConfig = SourceConfig()
    geometry: GeometryConfig = GeometryConfig()
    fields: list[FieldConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self) -> Profile:
        check_unique_ids(self.fields)
        return self
