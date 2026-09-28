"""Tiny i18n. English is canonical; Arabic mirrors every key. Missing keys fall back to English."""

from __future__ import annotations

import html
from typing import Any

from vigil.telegram.ui.texts import ar, en

LOCALES: dict[str, dict[str, str]] = {"en": en.T, "ar": ar.T}
SUPPORTED = ("en", "ar")


def t(lang: str, key: str, **kw: Any) -> str:
    table = LOCALES.get(lang) or en.T
    template = table.get(key) or en.T.get(key) or key
    if kw:
        try:
            return template.format(**kw)
        except (KeyError, IndexError):
            return template
    return template


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=False)


def missing_keys() -> dict[str, list[str]]:
    base = set(en.T)
    return {name: sorted(base - set(table)) for name, table in LOCALES.items() if name != "en"}
