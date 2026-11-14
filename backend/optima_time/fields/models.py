"""Field configuration (SPEC 11.1). One field = one value read from the board = one XML element."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from optima_time.fields.formats import (
    Align,
    ClockSpec,
    ClockStyle,
    ClockValue,
    NumberSpec,
    NumberStyle,
    NumberValue,
    PeriodSpec,
    align,
    parse_clock,
    parse_number,
    parse_period,
    render_clock,
    render_number,
    render_period,
)

# XML element name: ASCII, no spaces, doesn't start with a digit (SPEC 3.4, 11.1).
FIELD_ID_PATTERN = r"^[A-Za-z_][A-Za-z0-9_.\-]*$"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Roi(Model):
    """Rectangle relative to the rectified board image (0-1), so it survives resolution changes."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside(self) -> Roi:
        if self.x + self.w > 1 + 1e-6 or self.y + self.h > 1 + 1e-6:
            raise ValueError("ROI reaches outside the image")
        return self


class BlankPolicy(StrEnum):
    HOLD = "hold"  # keep the last valid value
    CLEAR = "clear"  # write an empty value after blank_delay_ms
    VALUE = "value"  # write blank_value


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"
    AUTO = "auto"


class EngineConfig(Model):
    name: Literal["ppocr"] = "ppocr"
    model: Literal["tiny", "small"] = "tiny"
    min_width: int = Field(default=160, ge=48, le=640)  # DECISIONS D9


class FieldBase(Model):
    id: str = Field(pattern=FIELD_ID_PATTERN, max_length=64)
    label: str = ""
    roi: Roi
    enabled: bool = True
    engine: EngineConfig = EngineConfig()
    margin: float = Field(default=0.15, ge=0, le=1)  # extra room around the ROI, times ROI height
    min_confidence: float = Field(default=0.5, ge=0, le=1)  # DECISIONS D10
    min_contrast: float = Field(default=40.0, ge=0, le=255)  # max-channel p99 - p10
    blank: BlankPolicy = BlankPolicy.HOLD
    blank_value: str = ""
    blank_delay_ms: int = Field(default=400, ge=0, le=10_000)
    align: Align = Align.NONE
    align_width: int = Field(default=0, ge=0, le=32)

    def aligned(self, text: str) -> str:
        return align(text, self.align, self.align_width)


class ClockField(FieldBase):
    type: Literal["clock"] = "clock"
    tenths: bool = False
    max_minutes: int = Field(default=999, ge=1, le=999)
    style: ClockStyle = ClockStyle.AS_IS
    direction: Direction = Direction.AUTO

    def spec(self) -> ClockSpec:
        return ClockSpec(tenths=self.tenths, max_minutes=self.max_minutes, style=self.style)

    def allowed_chars(self) -> str:
        return "0123456789:." if self.tenths else "0123456789:"

    def parse(self, text: str, last: ClockValue | NumberValue | None) -> ClockValue | None:
        return parse_clock(text, self.spec(), last if isinstance(last, ClockValue) else None)

    def render(self, value: ClockValue | NumberValue) -> str:
        assert isinstance(value, ClockValue)
        return self.aligned(render_clock(value, self.style))


class NumberField(FieldBase):
    type: Literal["number"] = "number"
    min_digits: int = Field(default=1, ge=1, le=6)
    max_digits: int = Field(default=2, ge=1, le=6)
    style: NumberStyle = NumberStyle.STRIP_ZEROS

    @model_validator(mode="after")
    def _digits(self) -> NumberField:
        if self.min_digits > self.max_digits:
            raise ValueError("min_digits > max_digits")
        return self

    def spec(self) -> NumberSpec:
        return NumberSpec(self.min_digits, self.max_digits, self.style)

    def allowed_chars(self) -> str:
        return "0123456789"

    def parse(self, text: str, last: ClockValue | NumberValue | None) -> NumberValue | None:
        return parse_number(text, self.spec())

    def render(self, value: ClockValue | NumberValue) -> str:
        assert isinstance(value, NumberValue)
        return self.aligned(render_number(value, self.spec()))


class PeriodField(FieldBase):
    type: Literal["period"] = "period"
    min_value: int = Field(default=1, ge=0, le=9)
    max_value: int = Field(default=4, ge=0, le=9)
    names: dict[int, str] = Field(default_factory=dict)

    def spec(self) -> PeriodSpec:
        return PeriodSpec(self.min_value, self.max_value, tuple(sorted(self.names.items())))

    def allowed_chars(self) -> str:
        return "0123456789"

    def parse(self, text: str, last: ClockValue | NumberValue | None) -> NumberValue | None:
        return parse_period(text, self.spec())

    def render(self, value: ClockValue | NumberValue) -> str:
        assert isinstance(value, NumberValue)
        return self.aligned(render_period(value, self.spec()))


FieldConfig = Annotated[ClockField | NumberField | PeriodField, Field(discriminator="type")]


def check_unique_ids(fields: list[ClockField | NumberField | PeriodField]) -> None:
    seen: set[str] = set()
    for f in fields:
        if f.id in seen:
            raise ValueError(f"duplicate field id {f.id!r}")
        seen.add(f.id)
