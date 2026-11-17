"""Values straight into a vMix title over the TCP API (port 8099), next to the XML file.

The vMix TCP API takes "FUNCTION <name> <query>\\r\\n" and answers "FUNCTION OK …" or
"FUNCTION ER <message>" (vMix help: TCP API; the query is the same as for the HTTP API). One
command at a time: each waits for its answer. Only changed values are sent; after a reconnect
everything is sent again. A field vMix refuses (a name the title doesn't have) is reported in
`problems` and not retried until its value changes, so one wrong name can't stall the rest.

  FUNCTION SetText Input=Skore&SelectedName=Time.Text&Value=12%3A02

Faster than the XML Data Source (vMix polls a file; here the change is pushed), and it doesn't
replace it: the XML stays the fallback.
"""

from __future__ import annotations

import contextlib
import logging
import socket
import time
from urllib.parse import quote

from optima_time.outputs.base import OutputWorker

log = logging.getLogger(__name__)

CONNECT_TIMEOUT_S = 1.0
ANSWER_TIMEOUT_S = 1.0
RECONNECT_MIN_S, RECONNECT_MAX_S = 1.0, 10.0  # back off while vMix isn't running


class VmixApiWorker(OutputWorker):
    name = "vmix_api"

    def __init__(
        self,
        host: str,
        port: int,
        title_input: str,
        suffix: str = ".Text",
        names: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.host, self.port, self.input = host, port, title_input
        self.suffix = suffix
        self.names = dict(names or {})  # field id -> title field name; empty = all fields
        self.target = f"vMix {host}:{port}, vstup {title_input}"
        self.problems: dict[str, str] = {}  # field id -> vMix's error
        self._sock: socket.socket | None = None
        self._buffer = b""
        self._sent: dict[str, str] = {}
        self._next_connect = 0.0
        self._backoff = RECONNECT_MIN_S

    def selected_name(self, field_id: str) -> str | None:
        if self.names:
            return self.names.get(field_id)
        return field_id + self.suffix

    def command(self, field_id: str, value: str) -> bytes | None:
        name = self.selected_name(field_id)
        if name is None:
            return None
        query = "&".join(
            f"{k}={quote(v, safe='')}"
            for k, v in (("Input", self.input), ("SelectedName", name), ("Value", value))
        )
        return f"FUNCTION SetText {query}\r\n".encode()

    # --- connection

    def _connect(self) -> socket.socket:
        if self._sock is not None:
            return self._sock
        wait = self._next_connect - time.monotonic()
        if wait > 0:  # this thread only writes to vMix: waiting here costs nothing else
            time.sleep(wait)
        try:
            sock = socket.create_connection((self.host, self.port), timeout=CONNECT_TIMEOUT_S)
        except OSError as error:
            self._next_connect = time.monotonic() + self._backoff
            self._backoff = min(RECONNECT_MAX_S, self._backoff * 2)
            raise ConnectionError(f"nejde se připojit k vMixu ({self.host}:{self.port})") from error
        self._backoff = RECONNECT_MIN_S
        sock.settimeout(ANSWER_TIMEOUT_S)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock, self._buffer, self._sent = sock, b"", {}  # a new connection: send everything
        log.info("connected to %s", self.target)
        return sock

    def _drop(self) -> None:
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
        self._sock = None
        self._next_connect = time.monotonic() + self._backoff

    def _answer(self, sock: socket.socket) -> str:
        """The next FUNCTION answer line; other lines (events) are skipped."""
        deadline = time.monotonic() + ANSWER_TIMEOUT_S
        while True:
            while b"\r\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\r\n", 1)
                text = line.decode("utf-8", "replace")
                if text.startswith("FUNCTION "):
                    return text
            if time.monotonic() > deadline:
                raise TimeoutError("vMix neodpověděl")
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("vMix ukončil spojení")
            self._buffer += chunk

    # --- OutputWorker

    def write(self, values: dict[str, str]) -> None:
        changed = {k: v for k, v in values.items() if self._sent.get(k) != v}
        if not changed:
            return
        sock = self._connect()
        try:
            for fid, value in changed.items():
                cmd = self.command(fid, value)
                if cmd is None:
                    self._sent[fid] = value
                    continue
                sock.sendall(cmd)
                answer = self._answer(sock)
                if answer.startswith("FUNCTION OK"):
                    self.problems.pop(fid, None)
                else:  # e.g. "FUNCTION ER Input not found": report, don't retry this value
                    self.problems[fid] = answer.removeprefix("FUNCTION ER").strip() or answer
                self._sent[fid] = value
        except (OSError, TimeoutError, ConnectionError):
            self._drop()
            raise

    def stop(self, final: dict[str, str] | None = None, timeout: float = 3.0) -> None:
        super().stop(final, timeout)
        self._drop()
