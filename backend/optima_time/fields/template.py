"""Derived output fields: templates over published values (SPEC 6, phase 2 "derived fields").

A template is text with placeholders. A placeholder names a field and can pass the value
through filters, left to right:

  {scoreh} : {scorea}                  "2 : 1"
  {penaltyh1|if:1;0}                   "1" while the penalty shows, else "0" (visibility)
  {period|map:1=1. třetina;2=2. třetina;3=3. třetina;*=Prodloužení}
  {scoreh|map:0=C:\\gfx\\0.png;*=C:\\gfx\\goal.png}     an image path per value
  {penaltya1|default:—}                "—" when empty
  {scoreh|pad:2}                       "02"
  {Time|nolead}                        "07:45" -> "7:45"
  {count:penaltyh1,penaltyh2}          "2" when both home penalties run (power play)
  {sum:foul1,foul2,foul3}              "2" when two foul lamps (indicators 1/0) are lit
  {{ and }}                            literal braces

Filters: default:X, if:A;B (A when not empty, else B), map:k=v;k=v;*=fallback (no match and no
* keeps the value), pad:N (zeros on the left), nolead (no leading zero), upper, lower.
Aggregates over several fields: count: (how many are on: not empty and not "0"), sum: (whole
numbers added up; empty or anything else counts 0). Filters can follow: {count:a,b|map:0=}.
Derived values are computed only from values that already passed confirmation, so they can't
carry a wrong reading further than the fields themselves (fail safe).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

PLACEHOLDER = re.compile(r"\{\{|\}\}|\{([^{}]*)\}")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


class TemplateError(ValueError):
    pass


def _default(value: str, arg: str) -> str:
    return value if value else arg


def _if(value: str, arg: str) -> str:
    yes, _, no = arg.partition(";")
    return yes if value else no


def _map(value: str, arg: str) -> str:
    fallback: str | None = None
    for pair in arg.split(";"):
        if "=" not in pair:
            continue
        key, _, out = pair.partition("=")
        if key == "*":
            fallback = out
        elif key == value:
            return out
    return value if fallback is None else fallback


def _pad(value: str, arg: str) -> str:
    try:
        width = int(arg)
    except ValueError as error:
        raise TemplateError(f"pad needs a number, got {arg!r}") from error
    return value.zfill(width) if value else value


def _nolead(value: str, _arg: str) -> str:
    stripped = value.lstrip("0")
    if not value:
        return value
    if not stripped or stripped[0] in ":.":  # "00:42" -> "0:42", "0" -> "0"
        return "0" + stripped
    return stripped


FILTERS: dict[str, Callable[[str, str], str]] = {
    "default": _default,
    "if": _if,
    "map": _map,
    "pad": _pad,
    "nolead": _nolead,
    "upper": lambda v, _a: v.upper(),
    "lower": lambda v, _a: v.lower(),
}


def _is_on(value: str) -> bool:
    return value not in ("", "0")


def _as_int(value: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        return 0


AGGREGATES: dict[str, Callable[[list[str]], str]] = {
    "count": lambda vs: str(sum(_is_on(v) for v in vs)),
    "sum": lambda vs: str(sum(_as_int(v) for v in vs)),
}


@dataclass(frozen=True)
class _Part:
    text: str  # literal text, or the field name for a placeholder
    filters: tuple[tuple[str, str], ...] = ()
    placeholder: bool = False
    aggregate: str = ""  # count / sum over `sources` instead of one field
    sources: tuple[str, ...] = ()


class Template:
    def __init__(self, source: str) -> None:
        self.source = source
        self.parts = self._parse(source)
        self.names = {n for p in self.parts if p.placeholder for n in (p.sources or (p.text,))}

    @staticmethod
    def _parse(source: str) -> list[_Part]:
        parts: list[_Part] = []
        pos = 0
        for m in PLACEHOLDER.finditer(source):
            if m.start() > pos:
                parts.append(_Part(source[pos : m.start()]))
            pos = m.end()
            token = m.group(0)
            if token in ("{{", "}}"):
                parts.append(_Part(token[0]))
                continue
            name, *chain = m.group(1).split("|")
            name = name.strip()
            aggregate, sources = "", ()
            head, colon, rest = name.partition(":")
            if colon and head.strip() in AGGREGATES:
                aggregate = head.strip()
                sources = tuple(n.strip() for n in rest.split(","))
                for n in sources:
                    if not NAME.match(n):
                        raise TemplateError(f"neplatný název pole {n!r} v {token}")
            elif not NAME.match(name):
                raise TemplateError(f"neplatný název pole {name!r} v {token}")
            filters = []
            for f in chain:
                fname, _, arg = f.partition(":")
                fname = fname.strip()
                if fname not in FILTERS:
                    raise TemplateError(f"neznámý filtr {fname!r} v {token}")
                filters.append((fname, arg))
            parts.append(_Part(name, tuple(filters), True, aggregate, sources))
        rest = source[pos:]
        if "{" in rest or "}" in rest:
            raise TemplateError("neuzavřená závorka { }")
        if rest:
            parts.append(_Part(rest))
        return parts

    def render(self, values: Mapping[str, str]) -> str:
        out = []
        for p in self.parts:
            if not p.placeholder:
                out.append(p.text)
                continue
            if p.aggregate:
                value = AGGREGATES[p.aggregate]([values.get(n, "") for n in p.sources])
            else:
                value = values.get(p.text, "")
            for fname, arg in p.filters:
                value = FILTERS[fname](value, arg)
            out.append(value)
        return "".join(out)


def check_template(source: str, known: set[str]) -> Template:
    """Parse and check that every placeholder names a known field."""
    t = Template(source)
    unknown = sorted(t.names - known)
    if unknown:
        raise TemplateError(f"šablona používá neexistující pole: {', '.join(unknown)}")
    # the filters run at render time; render once with blanks to catch bad arguments now
    t.render(dict.fromkeys(known, ""))
    return t
