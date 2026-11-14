import sys
import types

import pytest

from optima_time import window


class FakeWindow:
    def __init__(self) -> None:
        self.confirm_close = True
        self.calls: list[str] = []

    def destroy(self) -> None:
        self.calls.append("destroy")

    def restore(self) -> None:
        self.calls.append("restore")

    def show(self) -> None:
        self.calls.append("show")


@pytest.fixture
def fake_webview(monkeypatch):
    created: dict = {}
    mod = types.ModuleType("webview")

    def create_window(title, url, **kw):
        created.update(title=title, url=url, **kw)
        created["window"] = FakeWindow()
        return created["window"]

    def start(**kw):
        created["start"] = kw

    mod.create_window = create_window  # type: ignore[attr-defined]
    mod.start = start  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "webview", mod)
    return created


def test_window_runs_server_and_stops_it_when_closed(fake_webview):
    events: list[str] = []
    seen: list[window.AppWindow] = []
    shown = window.run_with_window(
        "http://127.0.0.1:8787/",
        lambda: events.append("start"),
        lambda: events.append("stop"),
        seen.append,
    )
    assert shown
    assert events == ["start", "stop"]
    assert fake_webview["url"] == "http://127.0.0.1:8787/"
    assert fake_webview["confirm_close"] is True  # closing stops vMix values: ask first
    assert fake_webview["start"]["localization"]["global.quit"] == "Ukončit"
    w = seen[0]
    w.show()
    w.close()
    fake = fake_webview["window"]
    assert fake.calls == ["restore", "show", "destroy"]
    assert fake.confirm_close is False  # tray "Ukončit" doesn't ask again


def test_without_pywebview_the_server_still_starts(monkeypatch):
    monkeypatch.setitem(sys.modules, "webview", None)  # import fails
    events: list[str] = []
    assert window.available() is not None
    shown = window.run_with_window(
        "u", lambda: events.append("start"), lambda: events.append("stop")
    )
    assert not shown
    assert events == ["start"]  # keeps running; the caller opens the browser


def test_window_failure_falls_back(fake_webview, monkeypatch):
    def broken(**_kw):
        raise OSError("WebView2 runtime missing")

    monkeypatch.setattr(sys.modules["webview"], "start", broken)
    events: list[str] = []
    shown = window.run_with_window(
        "u", lambda: events.append("start"), lambda: events.append("stop")
    )
    assert not shown
    assert events == ["start"]
