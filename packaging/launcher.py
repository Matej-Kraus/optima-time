"""Entry point of the packaged app (PyInstaller).

OptimaTime.exe runs without a console window: stdout/stderr are None there, so they are sent to
os.devnull (logs still go to %APPDATA%\\OptimaTime\\logs\\app.log). optima-time.exe is the same
program with a console, for the command line and --self-test.
"""

import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

from optima_time.cli import main

raise SystemExit(main())
