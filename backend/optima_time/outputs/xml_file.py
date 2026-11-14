"""The XML file vMix reads (SPEC 12.1).

Written only when a published value changes (never on a timer). Each write goes to a temp file
in the same folder which then replaces the target with os.replace(); the target is never held
open. vMix (or an antivirus) holding the target open makes the replace fail with PermissionError
on Windows: retry every few ms, switching to newer values if they arrive meanwhile. A write
taking longer than 250 ms is reported.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from optima_time.outputs.base import OutputWorker
from optima_time.outputs.xml import build_xml, parse_xml

log = logging.getLogger(__name__)

RETRY_SLEEP_S = 0.005
SLOW_WRITE_MS = 250.0
GIVE_UP_S = 5.0  # then the write counts as failed and the worker retries later


class XmlFileWorker(OutputWorker):
    name = "xml_file"

    def __init__(
        self,
        path: str | Path,
        newline: str = "\r\n",
        replace: Callable[[str, str], None] = os.replace,
    ) -> None:
        super().__init__()
        self.path = Path(path)
        self.newline = newline
        self._replace = replace  # injectable for tests (simulate a locked target)

    def read_existing(self) -> dict[str, str]:
        """The values in the file now (to start from them instead of blanking the graphic)."""
        try:
            return parse_xml(self.path.read_bytes())
        except (OSError, ValueError, SyntaxError):
            return {}

    def write(self, values: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.monotonic()
        retries = 0
        while True:
            fd, tmp = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(build_xml(values, self.newline))
                replaced, retries = self._replace_with_retry(tmp, t0, retries)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            if replaced:
                break
            newer = self.take_pending()  # newer values came while the target was locked
            if newer is not None:
                values = newer
        elapsed_ms = (time.monotonic() - t0) * 1000
        if elapsed_ms > SLOW_WRITE_MS:
            self.status.slow_writes += 1
            self.status.message = f"slow write: {elapsed_ms:.0f} ms, {retries} retries"
            log.warning("%s: %s", self.path, self.status.message)

    def _replace_with_retry(self, tmp: str, t0: float, retries: int) -> tuple[bool, int]:
        """(True, retries) once replaced; (False, retries) if newer values should go instead."""
        while True:
            try:
                self._replace(tmp, str(self.path))
                return True, retries
            except PermissionError:
                retries += 1
                if time.monotonic() - t0 > GIVE_UP_S:
                    raise
                if self.has_newer():
                    return False, retries
                time.sleep(RETRY_SLEEP_S)
