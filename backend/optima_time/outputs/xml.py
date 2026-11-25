"""The XML vMix reads as a Data Source (SPEC 5, 12.1).

Same shape as the file the reference app writes today: root <root>, one child element per field
(named by the field id, case kept), an empty value as an empty element (<penaltya1/>), fields in
a fixed ordinal order ("Time" before "penaltya1"), every enabled field always present so vMix's
columns never disappear. UTF-8 with a declaration until the real file says otherwise (D8).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

DECLARATION = '<?xml version="1.0" encoding="utf-8"?>'


def map_names(values: dict[str, str], names: dict[str, str]) -> dict[str, str]:
    """Map internal ids to XML element names. Profile validation prevents collisions."""
    return {names.get(field_id, field_id): value for field_id, value in values.items()}


def unmap_names(values: dict[str, str], names: dict[str, str]) -> dict[str, str]:
    """Map values read from an existing XML file back to internal ids."""
    reverse = {external: internal for internal, external in names.items()}
    return {reverse.get(name, name): value for name, value in values.items()}


def build_xml(values: dict[str, str], newline: str = "\r\n") -> bytes:
    lines = [DECLARATION, "<root>"]
    for name in sorted(values):
        value = values[name]
        lines.append(f"  <{name}>{escape(value)}</{name}>" if value else f"  <{name}/>")
    lines.append("</root>")
    return (newline.join(lines) + newline).encode("utf-8")


def parse_xml(data: bytes) -> dict[str, str]:
    """Values from an XML in this shape (used to start from the file's last values)."""
    root = ET.fromstring(data)
    if root.tag != "root":
        raise ValueError(f"root element is <{root.tag}>, expected <root>")
    return {child.tag: (child.text or "") for child in root}
