"""Read vMix titles and their fields from the Web API (port 8088).

Adapted from ScoreSight (https://github.com/royshil/scoresight),
src/vmix_discovery.py, MIT License, Copyright (c) 2024 OCC AI. See
THIRD_PARTY.md and LICENSES/ScoreSight-MIT.txt.

Discovery is read-only. Runtime values still use the XML Data Source or the
persistent TCP output in vmix_api.py.
"""

from __future__ import annotations

import http.client
import xml.etree.ElementTree as ET
from dataclasses import dataclass

DEFAULT_WEB_PORT = 8088
DEFAULT_TCP_PORT = 8099
TIMEOUT_S = 2.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class VmixDiscoveryError(Exception):
    """A connection or response problem that can be shown to the operator."""


@dataclass(frozen=True)
class Title:
    ref: str  # stable input key (GUID), falling back to its number
    number: str
    title: str
    kind: str
    selectors: tuple[str, ...]  # key, number and title: accepted vMix Input selectors
    fields: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "ref": self.ref,
            "number": self.number,
            "title": self.title,
            "kind": self.kind,
            "selectors": list(self.selectors),
            "fields": list(self.fields),
        }


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_titles(data: bytes | str) -> tuple[Title, ...]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise VmixDiscoveryError("vMix nevrátil platné XML z /api/.") from error
    if _local_name(root.tag) != "vmix":
        raise VmixDiscoveryError("Odpověď není stav vMixu (chybí kořen <vmix>).")
    inputs = next((node for node in root if _local_name(node.tag) == "inputs"), None)
    if inputs is None:
        raise VmixDiscoveryError("Odpověď vMixu neobsahuje <inputs>.")

    titles: list[Title] = []
    for node in inputs:
        if _local_name(node.tag) != "input":
            continue
        key = (node.get("key") or "").strip()
        number = (node.get("number") or "").strip()
        title = (node.get("title") or "").strip()
        ref = key or number
        if not ref:
            continue
        selectors = tuple(dict.fromkeys(value for value in (key, number, title) if value))
        fields = tuple(
            dict.fromkeys(
                name
                for child in node
                if _local_name(child.tag) == "text" and (name := (child.get("name") or "").strip())
            )
        )
        if fields:
            titles.append(
                Title(
                    ref=ref,
                    number=number,
                    title=title or f"Input {number or ref}",
                    kind=(node.get("type") or "").strip(),
                    selectors=selectors,
                    fields=fields,
                )
            )
    return tuple(titles)


def _validate_host(host: str) -> str:
    host = host.strip()
    if (
        not host
        or len(host) > 255
        or any(char.isspace() for char in host)
        or any(char in host for char in "/?#@")
        or "://" in host
    ):
        raise VmixDiscoveryError("Host vMixu musí být jen název nebo IP adresa.")
    return host


def fetch_titles(
    host: str,
    port: int = DEFAULT_WEB_PORT,
    *,
    timeout_s: float = TIMEOUT_S,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> tuple[Title, ...]:
    """Fetch and parse GET /api/ with bounded time and response size."""
    host = _validate_host(host)
    if not 1 <= port <= 65535:
        raise VmixDiscoveryError("Port vMixu musí být 1-65535.")

    connection = http.client.HTTPConnection(host, port, timeout=timeout_s)
    try:
        connection.request("GET", "/api/", headers={"Accept": "application/xml"})
        response = connection.getresponse()
        body = response.read(max_bytes + 1)
    except http.client.BadStatusLine as error:
        line = str(error)
        if "VERSION OK" in line or port == DEFAULT_TCP_PORT:
            raise VmixDiscoveryError(
                f"Port {port} je TCP API vMixu; pro Web API použij {DEFAULT_WEB_PORT}."
            ) from error
        raise VmixDiscoveryError(f"vMix vrátil neplatnou HTTP odpověď: {line[:120]}") from error
    except (OSError, TimeoutError, http.client.HTTPException) as error:
        raise VmixDiscoveryError(f"Nejde se připojit k vMixu ({host}:{port}): {error}") from error
    finally:
        connection.close()

    if len(body) > max_bytes:
        raise VmixDiscoveryError("Odpověď vMixu je neočekávaně velká.")
    if response.status == 401:
        raise VmixDiscoveryError(
            "vMix vyžaduje přihlášení (HTTP 401). Ve Web Controlleru povol přístup k API."
        )
    if response.status != 200:
        detail = body.decode("utf-8", "replace")[:200].strip()
        raise VmixDiscoveryError(f"vMix Web API vrátil HTTP {response.status}: {detail}")
    return parse_titles(body)


__all__ = ["Title", "VmixDiscoveryError", "fetch_titles", "parse_titles"]
