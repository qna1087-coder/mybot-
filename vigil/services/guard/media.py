"""Media policies per type, an allowed image count, and album (media group) aggregation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from vigil.services.guard.verdict import KIND_MEDIA, Verdict


def classify_media(message: Any) -> str | None:
    """Return the media type key, or None for plain text / non-media content."""
    if message.photo:
        return "photo"
    doc = message.document
    if doc is not None:
        mime = (doc.mime_type or "").lower()
        return "document_image" if mime.startswith("image/") else "document"
    if message.animation:
        return "animation"
    if message.video:
        return "video"
    if message.sticker:
        return "sticker"
    if message.video_note:
        return "video_note"
    if message.voice:
        return "voice"
    if message.audio:
        return "audio"
    if getattr(message, "paid_media", None) is not None:
        return "video"
    return None


@dataclass
class _Group:
    count: int = 0
    message_ids: list[int] = field(default_factory=list)
    first_seen: float = field(default_factory=time.monotonic)
    flagged: bool = False


class MediaGroupTracker:
    """In-memory counter per (chat, media_group_id). Albums arrive as separate updates."""

    def __init__(self, ttl_seconds: float = 900.0):
        self.ttl = ttl_seconds
        self._groups: dict[tuple[int, str, str], _Group] = {}

    def register(self, chat_id: int, group_id: str, media_type: str, message_id: int) -> _Group:
        key = (chat_id, group_id, media_type)
        g = self._groups.get(key)
        if g is None:
            g = _Group()
            self._groups[key] = g
        if message_id not in g.message_ids:
            g.message_ids.append(message_id)
            g.count += 1
        return g

    def purge(self) -> None:
        now = time.monotonic()
        stale = [k for k, g in self._groups.items() if now - g.first_seen > self.ttl]
        for k in stale:
            self._groups.pop(k, None)

    def __len__(self) -> int:
        return len(self._groups)


def check(message: Any, settings: Any, tracker: MediaGroupTracker) -> Verdict | None:
    media_type = classify_media(message)
    if media_type is None:
        return None
    policy = settings.media_policy_for(media_type)
    if policy == "allow":
        return None
    if policy == "block":
        return Verdict(kind=KIND_MEDIA, rule=f"media_guard:{media_type}", detail="blocked", severity="medium")

    # limited
    limit = int(settings.allowed_image_count or 0)
    group_id = message.media_group_id
    if group_id:
        g = tracker.register(message.chat.id, group_id, media_type, message.message_id)
        if g.count > limit:
            g.flagged = True
            return Verdict(
                kind=KIND_MEDIA,
                rule=f"media_guard:{media_type}_count",
                detail=f"{g.count}/{limit}",
                severity="medium",
                related_message_ids=list(g.message_ids),
            )
        return None
    if limit < 1:
        return Verdict(kind=KIND_MEDIA, rule=f"media_guard:{media_type}_count", detail=f"1/{limit}", severity="medium")
    return None
