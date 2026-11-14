"""Development and testing tools, run as `python -m tools.<name>`.

They print Czech text and symbols; a Windows console in cp1252 would crash on them (found by
CI on Windows), so output is switched to UTF-8 before any tool runs."""

from optima_time.cli import utf8_console

utf8_console()
