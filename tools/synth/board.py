"""Rendering of a full-colour LED video wall scoreboard as a camera sees it.

Layout after the photos from production (SPEC 5): green clock top centre, white "PERIÓDA" and
the period below it, "DOMÁCI" left and "HOSTIA" right with cyan scores under them, and two
penalty clocks per team at the bottom. Characters are drawn on a coarse LED grid with a
sans-serif font; every LED is a round dot, so the camera sees the LED raster (and moiré).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# LED grid of the wall
COLS, ROWS = 192, 112

# Field boxes on the LED grid: (x, y, w, h). The profile's ROIs are these boxes.
BOXES: dict[str, tuple[int, int, int, int]] = {
    "Time": (52, 3, 88, 30),
    "period": (86, 50, 20, 18),
    "scoreh": (8, 50, 46, 28),
    "scorea": (138, 50, 46, 28),
    "penaltyh1": (8, 82, 46, 13),
    "penaltyh2": (8, 97, 46, 13),
    "penaltya1": (138, 82, 46, 13),
    "penaltya2": (138, 97, 46, 13),
}
LABELS = {"PERIÓDA": (66, 37, 60, 11), "DOMÁCI": (4, 37, 54, 11), "HOSTIA": (134, 37, 54, 11)}

GREEN, CYAN, WHITE, YELLOW = (60, 255, 40), (255, 225, 30), (235, 235, 235), (30, 210, 255)
COLORS = {
    "Time": GREEN,
    "period": WHITE,
    "scoreh": CYAN,
    "scorea": CYAN,
    "penaltyh1": YELLOW,
    "penaltyh2": YELLOW,
    "penaltya1": YELLOW,
    "penaltya2": YELLOW,
}

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


@lru_cache(maxsize=64)
def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("no bold sans-serif TrueType font found; add one to FONT_CANDIDATES")


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int]) -> None:
    if not text:
        return
    x, y, w, h = box
    size = h + 4
    while size > 4:  # largest font whose text fits the box
        f = font(size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
        if right - left <= w and bottom - top <= h:
            break
        size -= 1
    f = font(size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
    pos = (x + (w - (right - left)) / 2 - left, y + (h - (bottom - top)) / 2 - top)
    draw.text(pos, text, font=f, fill=255)


@dataclass(frozen=True)
class LedStyle:
    pitch: int = 6  # camera-independent px per LED in the board image
    dot: float = 0.75  # dot diameter / pitch
    unlit: float = 0.06  # brightness of a dark LED
    font: str = "sans"  # values drawn as: sans (video wall) | seg7 | dot (5x7 dot matrix)


# 7-segment: which of a, b, c, d, e, f, g light up for each digit
SEGMENTS = {
    "0": "abcdef",
    "1": "bc",
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afgedc",
    "7": "abc",
    "8": "abcdefg",
    "9": "abcdfg",
}

# 5x7 dot-matrix glyphs, rows top to bottom
DOT5X7 = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    ":": ["0", "0", "1", "0", "1", "0", "0"],
    ".": ["0", "0", "0", "0", "0", "0", "1"],
}


def _draw_seg7(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int]) -> None:
    """Digits as 7-segment shapes on the LED grid, centered in the box."""
    x, y, w, h = box
    ch = h - 2
    cw = max(3, round(ch * 0.55))
    t = max(1, round(ch / 7))
    gap = max(1, round(cw * 0.3))
    widths = [cw if c.isdigit() else t + 1 for c in text]
    total = sum(widths) + gap * (len(text) - 1)
    cx, top = x + (w - total) // 2, y + 1
    for c, cwidth in zip(text, widths, strict=True):
        if c.isdigit():
            mid = top + ch // 2
            seg = {
                "a": (cx, top, cx + cw - 1, top + t - 1),
                "g": (cx, mid - t // 2, cx + cw - 1, mid - t // 2 + t - 1),
                "d": (cx, top + ch - t, cx + cw - 1, top + ch - 1),
                "f": (cx, top, cx + t - 1, mid),
                "e": (cx, mid, cx + t - 1, top + ch - 1),
                "b": (cx + cw - t, top, cx + cw - 1, mid),
                "c": (cx + cw - t, mid, cx + cw - 1, top + ch - 1),
            }
            for name in SEGMENTS[c]:
                draw.rectangle(seg[name], fill=255)
        elif c == ":":
            draw.rectangle((cx, top + ch // 3, cx + t - 1, top + ch // 3 + t - 1), fill=255)
            draw.rectangle((cx, top + 2 * ch // 3, cx + t - 1, top + 2 * ch // 3 + t - 1), fill=255)
        elif c == ".":
            draw.rectangle((cx, top + ch - t, cx + t - 1, top + ch - 1), fill=255)
        cx += cwidth + gap


def _draw_dot(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int]) -> None:
    """Digits from a 5x7 font; each font pixel is a k x k block of LEDs."""
    x, y, w, h = box
    k = max(1, h // 8)
    widths = [len(DOT5X7[c][0]) * k for c in text]
    gap = k
    total = sum(widths) + gap * (len(text) - 1)
    cx, top = x + (w - total) // 2, y + (h - 7 * k) // 2
    for c, cwidth in zip(text, widths, strict=True):
        for row, bits in enumerate(DOT5X7[c]):
            for col, bit in enumerate(bits):
                if bit == "1":
                    x0, y0 = cx + col * k, top + row * k
                    draw.rectangle((x0, y0, x0 + k - 1, y0 + k - 1), fill=255)
        cx += cwidth + gap


def led_board(texts: dict[str, str], style: LedStyle) -> np.ndarray:
    """The board image (BGR uint8), ROWS*pitch x COLS*pitch."""
    layers = np.zeros((ROWS, COLS, 3), np.float32)
    for name, box in {**BOXES, **LABELS}.items():
        text = texts.get(name, name if name in LABELS else "")
        if not text:
            continue
        mask = Image.new("L", (COLS, ROWS), 0)
        draw = ImageDraw.Draw(mask)
        if name in LABELS or style.font == "sans":
            _draw_centered(draw, text, box)
        elif style.font == "seg7":
            _draw_seg7(draw, text, box)
        else:
            _draw_dot(draw, text, box)
        alpha = np.asarray(mask, np.float32) / 255.0
        color = np.array(COLORS.get(name, WHITE), np.float32)
        layers = np.maximum(layers, alpha[..., None] * color)
    return _dots(layers, style)


def foreign_board(phase: float, style: LedStyle) -> np.ndarray:
    """Something other than the score: a goal animation (moving colours and a big text)."""
    yy, xx = np.mgrid[0:ROWS, 0:COLS].astype(np.float32)
    r = 127 + 127 * np.sin(xx / 9 + phase * 6)
    g = 127 + 127 * np.sin(yy / 7 - phase * 4)
    b = 127 + 127 * np.sin((xx + yy) / 13 + phase * 5)
    layers = np.stack([b, g, r], axis=2) * 0.6
    mask = Image.new("L", (COLS, ROWS), 0)
    _draw_centered(ImageDraw.Draw(mask), "GÓL!", (20 + int(10 * np.sin(phase * 3)), 25, 150, 60))
    alpha = np.asarray(mask, np.float32)[..., None] / 255.0
    layers = layers * (1 - alpha) + alpha * 255
    return _dots(layers, style)


@lru_cache(maxsize=8)
def _dot_mask(pitch: int, dot: float) -> np.ndarray:
    yy, xx = np.mgrid[0:pitch, 0:pitch]
    c = (pitch - 1) / 2
    return (((yy - c) ** 2 + (xx - c) ** 2) <= (dot * pitch / 2) ** 2).astype(np.float32)


def _dots(layers: np.ndarray, style: LedStyle) -> np.ndarray:
    lit = np.maximum(layers, style.unlit * 255)
    up = np.repeat(np.repeat(lit, style.pitch, axis=0), style.pitch, axis=1)
    mask = np.tile(_dot_mask(style.pitch, style.dot), (ROWS, COLS))
    return np.clip(up * mask[..., None], 0, 255).astype(np.uint8)


# --- camera ------------------------------------------------------------------------------


@dataclass(frozen=True)
class CameraStyle:
    frame: tuple[int, int] = (1920, 1080)
    corners: tuple[tuple[float, float], ...] = (
        (0.14, 0.16),
        (0.86, 0.19),
        (0.85, 0.83),
        (0.15, 0.80),
    )
    blur: float = 0.8  # Gaussian sigma in frame px
    noise: float = 3.0  # sensor noise sigma
    exposure: float = 1.0
    flicker: float = 0.03  # per-frame brightness jitter (LED PWM vs shutter)
    scan_band: bool = True  # a darker band rolling through the wall now and then


HARD = CameraStyle(
    corners=((0.30, 0.30), (0.68, 0.33), (0.67, 0.64), (0.31, 0.61)),
    blur=1.3,
    noise=6.0,
    exposure=0.75,
    flicker=0.08,
)


class Camera:
    def __init__(self, style: CameraStyle, board_shape: tuple[int, int], seed: int):
        self.style = style
        self.rng = np.random.default_rng(seed)
        self.random = random.Random(seed)
        w, h = style.frame
        bh, bw = board_shape
        src = np.array([(0, 0), (bw, 0), (bw, bh), (0, bh)], np.float32)
        dst = np.array([(x * w, y * h) for x, y in style.corners], np.float32)
        self.matrix = cv2.getPerspectiveTransform(src, dst)
        self.inverse = np.linalg.inv(self.matrix)
        self.board_shape = board_shape
        self.mask = cv2.warpPerspective(np.ones((bh, bw), np.float32), self.matrix, (w, h)) > 0.5
        grad = np.linspace(18, 34, h, dtype=np.float32)[:, None, None]
        texture = self.rng.normal(0, 4, (h // 8, w // 8, 3)).astype(np.float32)
        texture = cv2.resize(texture, (w, h), interpolation=cv2.INTER_LINEAR)
        self.background = np.clip(grad + texture, 0, 255).astype(np.float32)
        # Sensor noise from a small pool: generating 6 M normal samples per frame is slow.
        self.noise = [
            self.rng.normal(0, style.noise, (h, w, 3)).astype(np.float32) for _ in range(8)
        ]

    def shoot(
        self, board: np.ndarray, frame_index: int, occluder: float | None = None
    ) -> np.ndarray:
        """occluder: horizontal position 0-1 of a person walking in front of the board."""
        s = self.style
        w, h = s.frame
        warped = cv2.warpPerspective(board, self.matrix, (w, h), flags=cv2.INTER_AREA)
        frame = self.background.copy()
        frame[self.mask] = warped[self.mask]
        gain = s.exposure * (1 + self.rng.normal(0, s.flicker))
        if s.scan_band and (frame_index // 75) % 3 == 0:  # every third 3-second window
            y0 = int((frame_index % 25) / 25 * h)
            frame[max(0, y0 - 60) : y0 + 60] *= 0.8
        frame *= gain
        if occluder is not None:
            frame[self.occluder_mask(occluder)] = (24, 22, 26)
        if s.blur > 0:
            frame = cv2.GaussianBlur(frame, (0, 0), s.blur)
        frame += self.noise[int(self.rng.integers(len(self.noise)))]
        return np.clip(frame, 0, 255).astype(np.uint8)

    def occluder_mask(self, occluder: float) -> np.ndarray:
        """Frame pixels covered by a person standing at horizontal position `occluder` (0-1)."""
        w, h = self.style.frame
        mask = np.zeros((h, w), np.uint8)
        cx = int(occluder * w)
        cv2.ellipse(mask, (cx, int(h * 0.62)), (110, 330), 0, 0, 360, 255, -1)
        cv2.circle(mask, (cx, int(h * 0.22)), 70, 255, -1)
        return mask > 0

    def covered_boxes(
        self,
        occluder: float,
        boxes: dict[str, tuple[int, int, int, int]],
        pitch: int,
        margin: float,
    ) -> set[str]:
        """Board boxes (LED units) the person covers, each grown by margin x its height like
        the pipeline's crop."""
        frame_mask = self.occluder_mask(occluder).astype(np.uint8)
        bh, bw = self.board_shape
        board_mask = cv2.warpPerspective(
            frame_mask, self.inverse, (bw, bh), flags=cv2.INTER_NEAREST
        )
        out = set()
        for name, (x, y, bw_, bh_) in boxes.items():
            m = margin * bh_
            x0, y0 = int((x - m) * pitch), int((y - m) * pitch)
            x1, y1 = int((x + bw_ + m) * pitch), int((y + bh_ + m) * pitch)
            if board_mask[max(0, y0) : y1, max(0, x0) : x1].any():
                out.add(name)
        return out


def weave(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Interlaced frame: even lines from the first field, odd lines from the second 20 ms later."""
    out = first.copy()
    out[1::2] = second[1::2]
    return out
