"""Links, mentions and forwards — detected through Telegram entities, not naive text search."""

from __future__ import annotations

import re
from typing import Any

from vigil.services.guard.textutil import entity_text
from vigil.services.guard.verdict import KIND_FORWARD, KIND_LINK, KIND_MENTION, Verdict

LINK_ENTITY_TYPES = {"url", "text_link", "email"}
MENTION_ENTITY_TYPES = {"mention", "text_mention"}

# Backup patterns for things Telegram sometimes leaves un-entitied (e.g. inside code blocks).
_TG_LINK_RE = re.compile(r"(?i)(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog|tg://)[\w/?=&+.-]*")
_URL_RE = re.compile(r"(?i)\bhttps?://\S+|\bwww\.\S+\.\S+")


def _entities(message: Any) -> list[Any]:
    return list(message.entities or []) + list(message.caption_entities or [])


def check_links(message: Any, *, links: bool, mentions: bool) -> Verdict | None:
    text = message.text or message.caption or ""
    for e in _entities(message):
        if links and e.type in LINK_ENTITY_TYPES:
            shown = e.url if e.type == "text_link" else entity_text(text, e)
            rule = "link_guard:hidden_link" if e.type == "text_link" else f"link_guard:{e.type}"
            return Verdict(kind=KIND_LINK, rule=rule, detail=(shown or "")[:120], severity="high")
        if mentions and e.type in MENTION_ENTITY_TYPES:
            if e.type == "text_mention" and e.user is not None:
                shown = f"{e.user.first_name or ''} (id {e.user.id})".strip()
            else:
                shown = entity_text(text, e)
            return Verdict(kind=KIND_MENTION, rule=f"mention_guard:{e.type}", detail=shown[:120], severity="high")

    if links:
        lp = getattr(message, "link_preview_options", None)
        if lp is not None and getattr(lp, "url", None):
            return Verdict(kind=KIND_LINK, rule="link_guard:link_preview", detail=lp.url[:120], severity="high")
        markup = getattr(message, "reply_markup", None)
        if markup is not None and getattr(markup, "inline_keyboard", None):
            for row in markup.inline_keyboard:
                for btn in row:
                    if getattr(btn, "url", None):
                        return Verdict(kind=KIND_LINK, rule="link_guard:button_url", detail=btn.url[:120], severity="high")
        m = _TG_LINK_RE.search(text) or _URL_RE.search(text)
        if m and len(m.group(0)) > 4:
            return Verdict(kind=KIND_LINK, rule="link_guard:pattern", detail=m.group(0)[:120], severity="high")

    if mentions:
        via = getattr(message, "via_bot", None)
        if via is not None and getattr(via, "username", None):
            return Verdict(kind=KIND_MENTION, rule="mention_guard:via_bot", detail=f"@{via.username}", severity="medium")
    return None


def check_forward(message: Any) -> Verdict | None:
    origin = getattr(message, "forward_origin", None)
    if origin is None:
        return None
    if getattr(message, "is_automatic_forward", False):
        return None
    otype = getattr(origin, "type", "unknown")
    detail = ""
    chat = getattr(origin, "chat", None)
    if chat is not None:
        detail = chat.title or (f"@{chat.username}" if getattr(chat, "username", None) else str(chat.id))
    sender = getattr(origin, "sender_user", None)
    if sender is not None:
        detail = sender.first_name or str(sender.id)
    if not detail:
        detail = getattr(origin, "sender_user_name", "") or otype
    return Verdict(kind=KIND_FORWARD, rule=f"forward_guard:{otype}", detail=str(detail)[:120], severity="medium")
