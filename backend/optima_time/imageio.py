"""Image files by path, safe for non-ASCII paths.

On Windows cv2.imread / cv2.imwrite can't open a path with characters outside the ANSI code
page (e.g. C:\\Users\\Matěj\\...): imread returns None, imwrite returns False. Reading and
writing the bytes in Python and en/decoding them in memory works everywhere.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt


def read_image(path: str | Path, flags: int = cv2.IMREAD_COLOR) -> npt.NDArray[np.uint8] | None:
    """Like cv2.imread: None when the file is missing or isn't an image."""
    try:
        raw = np.fromfile(Path(path), np.uint8)
    except OSError:
        return None
    if raw.size == 0:
        return None
    image = cv2.imdecode(raw, flags)
    return None if image is None else np.asarray(image, np.uint8)


def write_image(path: str | Path, image: npt.ArrayLike) -> bool:
    """Like cv2.imwrite: the format follows the suffix; False when it can't be written."""
    path = Path(path)
    ok, data = cv2.imencode(path.suffix or ".png", np.asarray(image))
    if not ok:
        return False
    try:
        path.write_bytes(data.tobytes())
    except OSError:
        return False
    return True
