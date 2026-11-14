"""Reading the XML file while the writer may be replacing it.

On Windows, opening a file at the instant os.replace() swaps it in fails with PermissionError
(the old file is pending deletion). vMix meets the same and reads again at its next interval;
the tests do the same instead of failing (DECISIONS D29)."""

import time
from pathlib import Path

from optima_time.outputs.xml import parse_xml


def read_values(path: Path, attempts: int = 50) -> dict[str, str]:
    for _ in range(attempts - 1):
        try:
            return parse_xml(path.read_bytes())
        except PermissionError:
            time.sleep(0.01)
    return parse_xml(path.read_bytes())


def read_bytes(path: Path, attempts: int = 50) -> bytes:
    for _ in range(attempts - 1):
        try:
            return path.read_bytes()
        except PermissionError:
            time.sleep(0.01)
    return path.read_bytes()
