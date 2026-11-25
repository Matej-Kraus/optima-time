from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from optima_time.outputs.vmix_discovery import (
    VmixDiscoveryError,
    fetch_titles,
    parse_titles,
)

VMIX_XML = b"""<?xml version="1.0"?>
<vmix>
  <preview>1</preview><active>2</active>
  <inputs>
    <input key="key-score" number="1" type="GT" title="Score">
      <text index="0" name="Time.Text">12:34</text>
      <text index="1" name="Home.Text">2</text>
      <text index="2" name="Home.Text">2</text>
    </input>
    <input key="key-camera" number="2" type="Capture" title="Camera"/>
  </inputs>
</vmix>
"""


def test_parse_titles_returns_stable_refs_and_unique_fields() -> None:
    titles = parse_titles(VMIX_XML)
    assert len(titles) == 1
    title = titles[0]
    assert title.ref == "key-score"
    assert title.selectors == ("key-score", "1", "Score")
    assert title.fields == ("Time.Text", "Home.Text")
    assert title.as_dict()["title"] == "Score"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ("not xml", "platné XML"),
        ("<root/>", "kořen <vmix>"),
        ("<vmix/>", "<inputs>"),
    ],
)
def test_parse_titles_has_actionable_errors(data: str, message: str) -> None:
    with pytest.raises(VmixDiscoveryError, match=message):
        parse_titles(data)


@contextmanager
def http_server(body: bytes, status: int = 200) -> Iterator[int]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            assert self.path == "/api/"
            self.send_response(status)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_fetch_titles_from_web_api() -> None:
    with http_server(VMIX_XML) as port:
        titles = fetch_titles("127.0.0.1", port)
    assert [title.title for title in titles] == ["Score"]


def test_fetch_titles_reports_auth_and_response_limit() -> None:
    with http_server(b"login", 401) as port, pytest.raises(VmixDiscoveryError, match="HTTP 401"):
        fetch_titles("127.0.0.1", port)
    with (
        http_server(VMIX_XML) as port,
        pytest.raises(VmixDiscoveryError, match="neočekávaně velká"),
    ):
        fetch_titles("127.0.0.1", port, max_bytes=10)


def test_fetch_titles_recognizes_tcp_port_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Don't open a real TCP socket: on Windows the peer can abort before http.client
    # surfaces BadStatusLine("VERSION OK …"), which is the path we care about.
    import http.client

    def fake_request(self: http.client.HTTPConnection, *args: object, **kwargs: object) -> None:
        del self, args, kwargs
        raise http.client.BadStatusLine("VERSION OK 28.0.0.0")

    monkeypatch.setattr(http.client.HTTPConnection, "request", fake_request)
    with pytest.raises(VmixDiscoveryError, match="TCP API"):
        fetch_titles("127.0.0.1", 8099)


def test_fetch_titles_rejects_urls_in_host() -> None:
    with pytest.raises(VmixDiscoveryError, match="název nebo IP"):
        fetch_titles("http://127.0.0.1", 8088)
