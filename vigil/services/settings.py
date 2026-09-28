"""Per-channel settings layered over global defaults, with a tiny cache."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.repo import settings as repo
from vigil.services.context import Services

MEDIA_TYPES: tuple[str, ...] = (
    "photo",
    "document_image",
    "document",
    "video",
    "animation",
    "sticker",
    "video_note",
    "voice",
    "audio",
)

MEDIA_POLICY_VALUES: tuple[str, ...] = ("allow", "limited", "block")

MODERATION_CATEGORIES: tuple[str, ...] = (
    "sexual",
    "minors",
    "drugs",
    "violence",
    "hate",
    "harassment",
    "self_harm",
    "weapons",
    "extremism",
    "scam",
    "other",
)

DEFAULTS: dict[str, Any] = {
    "guard_enabled": True,
    "links_guard": True,
    "mentions_guard": True,
    "forwards_guard": True,
    "media_guard": True,
    "allowed_image_count": 1,
    "media_policy": {
        "photo": "limited",  # limited = up to allowed_image_count per post/album
        "document_image": "block",
        "document": "block",
        "video": "block",
        "animation": "block",
        "sticker": "block",
        "video_note": "block",
        "voice": "block",
        "audio": "block",
    },
    "emoji_guard": True,
    "language_guard": True,  # non-Arabic, non-Latin scripts → violation
    "english_moderation": True,  # Latin text → moderation API
    "foreign_latin_violation": True,  # API reports non-English Latin text → violation
    "english_char_limit": 75,
    "length_action": "delete",  # delete | demote
    "violation_action": "demote",  # demote | delete_only | notify_only
    "delete_offending_message": True,
    "api_fail_mode": "default",  # default (global) | open | closed
    "notify_system_owner": False,
    "moderation_categories": list(MODERATION_CATEGORIES),
    "unattributed_alerts": True,
}


class ChannelSettings:
    def __init__(self, data: dict[str, Any]):
        self._d = data

    def __getattr__(self, item: str) -> Any:
        try:
            return self._d[item]
        except KeyError as e:
            raise AttributeError(item) from e

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)

    def media_policy_for(self, media_type: str) -> str:
        return (self._d.get("media_policy") or {}).get(media_type, "block")

    def as_dict(self) -> dict[str, Any]:
        return dict(self._d)


class ChannelSettingsService:
    def __init__(self, ctx: Services):
        self.ctx = ctx
        self._cache: dict[int, dict[str, Any]] = {}

    async def get(self, s: AsyncSession, channel_id: int) -> ChannelSettings:
        if channel_id in self._cache:
            return ChannelSettings(copy.deepcopy(self._cache[channel_id]))
        merged = copy.deepcopy(DEFAULTS)
        for scope in (0, channel_id):
            values = await repo.get_all(s, scope)
            for k, v in values.items():
                if k not in merged:
                    continue
                if isinstance(merged[k], dict) and isinstance(v, dict):
                    merged[k] = {**merged[k], **v}
                else:
                    merged[k] = v
        self._cache[channel_id] = merged
        return ChannelSettings(copy.deepcopy(merged))

    async def set(self, s: AsyncSession, channel_id: int, key: str, value: Any, by: int | None) -> None:
        if key not in DEFAULTS:
            raise KeyError(key)
        await repo.set_value(s, channel_id, key, value, by)
        self.invalidate(channel_id)

    async def set_media_policy(self, s: AsyncSession, channel_id: int, media_type: str, policy: str, by: int | None) -> None:
        current = (await self.get(s, channel_id)).media_policy
        current[media_type] = policy
        await self.set(s, channel_id, "media_policy", current, by)

    async def toggle(self, s: AsyncSession, channel_id: int, key: str, by: int | None) -> bool:
        current = bool((await self.get(s, channel_id)).get(key))
        await self.set(s, channel_id, key, not current, by)
        return not current

    def invalidate(self, channel_id: int | None = None) -> None:
        if channel_id is None or channel_id == 0:
            self._cache.clear()
        else:
            self._cache.pop(channel_id, None)
