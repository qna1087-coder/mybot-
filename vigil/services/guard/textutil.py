"""Telegram entity offsets are UTF-16 code units. Everything here respects that."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _utf16(text: str) -> bytes:
    return text.encode("utf-16-le")


def entity_text(text: str, entity: Any) -> str:
    data = _utf16(text)
    start = entity.offset * 2
    end = (entity.offset + entity.length) * 2
    return data[start:end].decode("utf-16-le", errors="ignore")


def strip_entities(text: str, entities: Iterable[Any], types: set[str]) -> str:
    """Remove the spans of the given entity types (URLs, mentions …) before language analysis."""
    data = _utf16(text)
    spans = sorted(
        ((e.offset * 2, (e.offset + e.length) * 2) for e in entities if e.type in types),
        reverse=True,
    )
    for start, end in spans:
        data = data[:start] + b" \x00" + data[end:]
    return data.decode("utf-16-le", errors="ignore")


def excerpt(text: str | None, limit: int = 500) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
