"""Premium / custom emoji: allowlist by custom_emoji_id, resolved from entities (never from text)."""

from __future__ import annotations

from typing import Any

from vigil.services.guard.textutil import entity_text
from vigil.services.guard.verdict import KIND_EMOJI, Verdict


def extract_custom_emoji(message: Any) -> list[tuple[str, str]]:
    """[(custom_emoji_id, visible_emoji)] in order of appearance."""
    out: list[tuple[str, str]] = []
    for text, ents in ((message.text, message.entities), (message.caption, message.caption_entities)):
        if not ents:
            continue
        for e in ents:
            if e.type == "custom_emoji" and e.custom_emoji_id:
                out.append((str(e.custom_emoji_id), entity_text(text or "", e)))
    return out


def check(message: Any, allowed_ids: set[str]) -> Verdict | None:
    found = extract_custom_emoji(message)
    if not found:
        return None
    bad = [(cid, em) for cid, em in found if cid not in allowed_ids]
    if not bad:
        return None
    shown = " ".join(em for _, em in bad[:5])
    ids = ", ".join(cid for cid, _ in bad[:3])
    return Verdict(
        kind=KIND_EMOJI,
        rule="emoji_guard:not_in_allowlist",
        detail=f"{shown} · {ids}"[:200],
        severity="medium",
    )
