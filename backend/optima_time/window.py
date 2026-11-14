"""The app's own window (instead of a browser tab) for the packaged Windows app.

pywebview (BSD-3-Clause, see THIRD_PARTY.md) shows the same UI as the browser in a native window
(Edge WebView2 on Windows). The window must run on the main thread, so the web server runs in a
background thread while it is open. Closing the window asks first, because it stops the values
going to vMix. Without pywebview or WebView2 the caller falls back to the browser.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

TITLE = "Optima Time"
BACKGROUND = "#0a0e19"  # --bg-core of the UI, so the window doesn't flash white while loading

# Czech texts of the window's own dialogs (pywebview localization keys)
LOCALIZATION = {
    "global.quitConfirmation": "Ukončit Optima Time? Grafika ve vMixu přestane dostávat hodnoty.",
    "global.ok": "OK",
    "global.quit": "Ukončit",
    "global.cancel": "Zrušit",
    "global.saveFile": "Uložit soubor",
    "windows.fileFilter.allFiles": "Všechny soubory",
    "windows.fileFilter.otherFiles": "Ostatní soubory",
}


def available() -> str | None:
    """None when the window can be shown, otherwise why not (for the log and the self-test)."""
    try:
        import webview  # noqa: F401  # pyright: ignore[reportMissingImports]
    except ImportError as error:
        return f"pywebview is not installed ({error})"
    return None


WEBVIEW2_KEY = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def webview2_version() -> str | None:
    """Version of the Edge WebView2 runtime (Windows), None when it isn't installed."""
    if sys.platform != "win32":
        return None
    import winreg

    places = [
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\" + WEBVIEW2_KEY),
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\" + WEBVIEW2_KEY),
        (winreg.HKEY_CURRENT_USER, "SOFTWARE\\" + WEBVIEW2_KEY),
    ]
    for root, key in places:
        try:
            with winreg.OpenKey(root, key) as k:
                version = str(winreg.QueryValueEx(k, "pv")[0])
        except OSError:
            continue
        if version and version != "0.0.0.0":
            return version
    return None


def check() -> str:
    """Self-test: can the window be shown here? Raises with the reason when not."""
    reason = available()
    if reason:
        raise RuntimeError(reason)
    if sys.platform != "win32":
        return "pywebview ok"
    import webview.platforms.winforms  # noqa: F401  # pyright: ignore[reportMissingImports]

    version = webview2_version()
    if not version:
        raise RuntimeError("chybí Edge WebView2 Runtime, UI se otevře v prohlížeči")
    return f"WebView2 {version}"


class AppWindow:
    """One native window with the UI. `run()` blocks until the window is closed."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._window: Any = None

    def run(self) -> None:
        import webview  # pyright: ignore[reportMissingImports]

        self._window = webview.create_window(
            TITLE,
            self.url,
            width=1440,
            height=900,
            min_size=(1000, 680),
            maximized=True,
            confirm_close=True,
            background_color=BACKGROUND,
            text_select=True,
            zoomable=True,
        )
        webview.start(localization=LOCALIZATION, private_mode=False)

    def show(self) -> None:
        """Bring the window back (tray "Otevřít okno")."""
        w = self._window
        if w is not None:
            w.restore()
            w.show()

    def close(self) -> None:
        """Close without asking (tray "Ukončit" already decided)."""
        w = self._window
        if w is not None:
            w.confirm_close = False
            w.destroy()


def run_with_window(
    url: str,
    start_server: Callable[[], None],
    stop_server: Callable[[], None],
    on_window: Callable[[AppWindow], None] = lambda _w: None,
) -> bool:
    """Start the server, show the window, stop the server when the window closes.

    Returns False when the window couldn't be shown; the server keeps running then and the
    caller opens the browser instead.
    """
    reason = available()
    if reason:
        log.warning("no app window, using the browser: %s", reason)
        start_server()
        return False
    window = AppWindow(url)
    on_window(window)
    start_server()
    try:
        window.run()
    except Exception:
        log.exception("app window failed, using the browser")
        return False
    stop_server()
    return True
