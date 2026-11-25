"""Profile: settings for one hall and sport (SPEC 2, 14.1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from optima_time.fields.models import FIELD_ID_PATTERN, FieldConfig, Model, Roi, check_unique_ids
from optima_time.fields.template import TemplateError, check_template

SCHEMA_VERSION = 2


class Deinterlace(StrEnum):
    NONE = "none"
    BLEND = "blend"  # average neighbouring lines: steady, slightly soft
    BOB = "bob"  # keep one field, stretch it: sharp, half vertical resolution


class SourceConfig(Model):
    type: Literal["file", "ndi", "device", "stream"] = "file"
    # file / image
    path: str = ""
    loop: bool = True
    speed: float = Field(default=1.0, ge=0)  # 1 = real time, 0 = as fast as possible
    # network stream (SRT, RTSP, RTMP, UDP, HTTP)
    url: str = Field(default="", max_length=2000)
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
    # the board's real width / height; 0 = as the corners show it. Set it when the camera
    # sees the board at an angle, so the straightened board isn't squeezed.
    aspect: float = Field(default=0.0, ge=0.0, le=10.0)

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


XmlName = Annotated[str, Field(pattern=FIELD_ID_PATTERN, max_length=64)]


class XmlFileOutput(Model):
    enabled: bool = True
    path: str = ""
    newline: NewLine = NewLine.CRLF
    clear_on_exit: bool = False  # else the last values stay in the file
    # Internal field/derived id -> XML element name. Empty means identity (old profiles).
    names: dict[XmlName, XmlName] = Field(default_factory=dict)


class VmixAction(StrEnum):
    """What a vMix command does with its value (vMix Shortcut Function Reference, Title)."""

    TEXT = "text"  # SetText: the value as text
    IMAGE = "image"  # SetImage: the value is a file path or URL ("" clears the image)
    TEXT_VISIBLE = "text_visible"  # SetTextVisibleOn / Off: shown while the value is on
    IMAGE_VISIBLE = "image_visible"  # SetImageVisibleOn / Off: shown while the value is on
    TEXT_COLOUR = "text_colour"  # SetTextColour: the value is #RRGGBB
    COLOR = "color"  # SetColor: the value is #AARRGGBB or #RRGGBB (shapes, backgrounds)


class VmixCommand(Model):
    """One field or derived field driving one element of a vMix title, e.g. the penalty
    background shown only while a penalty runs: penaltyh1 -> image_visible -> PozadiH.Source."""

    value: str = Field(pattern=FIELD_ID_PATTERN, max_length=64)  # field or derived field id
    action: VmixAction = VmixAction.TEXT
    target: str = Field(min_length=1, max_length=200)  # SelectedName in the title
    input: str = Field(default="", max_length=200)  # another title; "" = the output's title
    enabled: bool = True


class VmixApiOutput(Model):
    """Values pushed into a vMix title over the TCP API (outputs/vmix_api.py)."""

    enabled: bool = False
    host: str = Field(default="127.0.0.1", max_length=255)
    web_port: int = Field(default=8088, ge=1, le=65535)  # read-only title/field discovery
    port: int = Field(default=8099, ge=1, le=65535)
    input: str = Field(default="", max_length=200)  # title: number, name or key
    suffix: str = Field(default=".Text", max_length=20)  # field id + suffix = title field
    names: dict[str, str] = Field(default_factory=dict)  # explicit id -> title field; only these
    commands: list[VmixCommand] = Field(default_factory=list, max_length=100)  # images etc.


class OutputsConfig(Model):
    xml_file: XmlFileOutput = XmlFileOutput()
    vmix_api: VmixApiOutput = VmixApiOutput()
    # Hold every value back by this long, so the graphic changes together with a delayed
    # picture (e.g. the scoreboard camera delayed in vMix). Pause and test data act at once.
    delay_ms: int = Field(default=0, ge=0, le=10_000)


class BlendMode(StrEnum):
    MAX = "max"  # keeps LEDs lit when the camera catches them dark (PWM flicker)
    MEAN = "mean"  # smooths noise and moiré


class PreprocessConfig(Model):
    """Optional blending of the last N frames against LED flicker and moiré (SPEC 9.2).
    Off by default: it delays changes by up to N-1 frames."""

    blend_frames: int = Field(default=1, ge=1, le=5)  # 1 = off
    blend_mode: BlendMode = BlendMode.MAX


class ImageConfig(Model):
    """Picture adjustments of the straightened board, before the guard and the reading
    (like the controls of a camera). All neutral by default. They can't bring back what the
    camera blew out to white: get the exposure right on the camera first."""

    brightness: int = Field(default=0, ge=-100, le=100)  # -100..100 (% of half the range)
    contrast: float = Field(default=1.0, ge=0.2, le=3.0)  # 1 = unchanged
    gamma: float = Field(default=1.0, ge=0.3, le=3.0)  # >1 brightens dark tones
    sharpen: float = Field(default=0.0, ge=0.0, le=3.0)  # unsharp mask strength
    net_removal: int = Field(default=0, ge=0, le=6)  # px: fills thin dark lines (a net)
    invert: bool = False  # dark digits on a light board

    def neutral(self) -> bool:
        return self == ImageConfig()


class DetectionConfig(Model):
    """Read a field only when its crop changed (SPEC 10.5)."""

    enabled: bool = True
    threshold: float = Field(default=0.15, ge=0, le=5)  # preprocess.difference (D22)
    max_age_ms: int = Field(default=1000, ge=100, le=10_000)  # read at least this often


class DerivedField(Model):
    """An extra output value made from published fields by a template (fields/template.py),
    e.g. "{scoreh} : {scorea}". Written to the XML like a field."""

    id: str = Field(pattern=FIELD_ID_PATTERN, max_length=64)
    template: str = Field(default="", max_length=2000)
    enabled: bool = True


class Profile(Model):
    schema_version: Literal[2] = SCHEMA_VERSION
    name: str = "profil"
    source: SourceConfig = SourceConfig()
    geometry: GeometryConfig = GeometryConfig()
    fields: list[FieldConfig] = Field(default_factory=list)
    derived: list[DerivedField] = Field(default_factory=list)
    preprocess: PreprocessConfig = PreprocessConfig()
    image: ImageConfig = ImageConfig()
    guard: GuardConfig = GuardConfig()
    detection: DetectionConfig = DetectionConfig()
    outputs: OutputsConfig = OutputsConfig()

    @model_validator(mode="after")
    def _unique(self) -> Profile:
        check_unique_ids(self.fields)
        known = {f.id for f in self.fields}
        for d in self.derived:
            if d.id in known:
                raise ValueError(f"odvozené pole {d.id!r}: tento název už má jiné pole")
            try:
                check_template(d.template, {f.id for f in self.fields})
            except TemplateError as error:
                raise ValueError(f"odvozené pole {d.id!r}: {error}") from error
            known.add(d.id)
        xml_names = self.outputs.xml_file.names
        unknown = set(xml_names) - known
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"mapování XML: neexistující pole {names}")
        effective = [xml_names.get(name, name) for name in known]
        if len(effective) != len(set(effective)):
            raise ValueError("mapování XML: názvy výstupních prvků musí být jedinečné")
        for c in self.outputs.vmix_api.commands:
            if c.value not in known:
                raise ValueError(f"příkaz pro vMix ({c.target}): neexistující pole {c.value!r}")
        return self
