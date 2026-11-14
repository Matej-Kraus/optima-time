"""Keep the PC awake while the app runs (SPEC 14.3). Windows only; a no-op elsewhere.

SetThreadExecutionState with ES_CONTINUOUS applies as long as the calling thread lives, so it is
called from the long-lived supervisor thread. The display may still turn off; the system may not
sleep.
"""

from __future__ import annotations

import ctypes
import logging
import sys

log = logging.getLogger(__name__)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_awake(on: bool) -> bool:
    """Returns True if the request was made (Windows), False elsewhere."""
    if sys.platform != "win32":
        return False
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
    try:
        result = ctypes.windll.kernel32.SetThreadExecutionState(flags)  # type: ignore[attr-defined]
    except (AttributeError, OSError) as error:
        log.warning("can't keep the PC awake: %s", error)
        return False
    return bool(result)
