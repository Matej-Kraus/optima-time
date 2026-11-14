"""Notification-area icon of the packaged Windows app (SPEC 14.2): open the UI, quit.

pystray (LGPLv3, see THIRD_PARTY.md) runs detached on Windows. Elsewhere this is a no-op: the
console stays and Ctrl+C stops the app.
"""

from __future__ import annotations

import logging
import sys
import webbrowser
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)


def _icon_image():
    from PIL import Image, ImageDraw

    bundle = getattr(sys, "_MEIPASS", None)
    if bundle and (Path(bundle) / "icon.png").exists():
        return Image.open(Path(bundle) / "icon.png")

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 10, 62, 54), radius=8, fill=(17, 20, 24, 255), outline=(61, 220, 132))
    d.text((12, 22), "12:34", fill=(61, 220, 132))
    return img


class Tray:
    """The running icon: `notify()` shows a Windows notification, `stop()` removes the icon."""

    def __init__(self, icon) -> None:
        self._icon = icon

    def notify(self, title: str, message: str, _problem: bool = True) -> None:
        self._icon.notify(message or title, title)

    def stop(self) -> None:
        self._icon.stop()


def start_tray(
    url: str, on_quit: Callable[[], None], on_open: Callable[[], None] | None = None
) -> Tray | None:
    """Show the icon; returns it, or None where unsupported.
    `on_open` brings up the UI (the app window); without it the browser opens."""
    if sys.platform != "win32":
        return None
    try:
        import pystray
    except ImportError as error:
        log.warning("no tray icon: %s", error)
        return None

    def quit_app(icon, _item) -> None:
        icon.stop()
        on_quit()

    def open_ui(_icon, _item) -> None:
        if on_open is not None:
            on_open()
        else:
            webbrowser.open(url)

    icon = pystray.Icon(
        "optima-time",
        _icon_image(),
        "Optima Time",
        menu=pystray.Menu(
            pystray.MenuItem("Otevřít Optima Time", open_ui, default=True),
            pystray.MenuItem("Ukončit", quit_app),
        ),
    )
    icon.run_detached()
    return Tray(icon)
