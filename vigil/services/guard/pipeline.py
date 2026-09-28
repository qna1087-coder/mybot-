"""Layered evaluation, cheapest first. The first violation wins.

media → custom emoji → forwards → links/mentions → script → length → wordlist → moderation API
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.errors import ModerationUnavailable
from vigil.db.models import Channel
from vigil.db.repo import emoji as emoji_repo
from vigil.services.context import Services
from vigil.services.guard import emoji as emoji_guard
from vigil.services.guard import language as lang
from vigil.services.guard import length as length_guard
from vigil.services.guard import links as link_guard
from vigil.services.guard import media as media_guard
from vigil.services.guard import wordlist
from vigil.services.guard.links import LINK_ENTITY_TYPES, MENTION_ENTITY_TYPES
from vigil.services.guard.textutil import excerpt, strip_entities
from vigil.services.guard.verdict import KIND_CONTENT, KIND_LANGUAGE, Verdict
from vigil.services.settings import ChannelSettings

log = logging.getLogger("vigil.guard")


class GuardPipeline:
    def __init__(self, ctx: Services):
        self.ctx = ctx

    async def evaluate(self, s: AsyncSession, ch: Channel, message: Any, settings: ChannelSettings) -> Verdict | None:
        if not settings.guard_enabled:
            return None

        text = message.text or message.caption or ""
        entities = list(message.entities or []) + list(message.caption_entities or [])

        # 1. media
        if settings.media_guard:
            v = media_guard.check(message, settings, self.ctx.media_groups)
            if v:
                return self._with_excerpt(v, text)

        # 2. custom emoji
        if settings.emoji_guard:
            allowed = await emoji_repo.allowed_ids(s, ch.id)
            v = emoji_guard.check(message, allowed)
            if v:
                return self._with_excerpt(v, text)

        # 3. forwards
        if settings.forwards_guard:
            v = link_guard.check_forward(message)
            if v:
                return self._with_excerpt(v, text)

        # 4. links & mentions
        if settings.links_guard or settings.mentions_guard:
            v = link_guard.check_links(message, links=settings.links_guard, mentions=settings.mentions_guard)
            if v:
                return self._with_excerpt(v, text)

        if not text.strip():
            return None

        # 5. script analysis (local)
        clean = strip_entities(text, entities, LINK_ENTITY_TYPES | MENTION_ENTITY_TYPES | {"hashtag", "cashtag", "bot_command"})
        profile = lang.analyze(clean)
        if settings.language_guard and profile.is_foreign_script:
            return self._with_excerpt(
                Verdict(
                    kind=KIND_LANGUAGE,
                    rule="language_guard:foreign_script",
                    detail="".join(profile.other_samples),
                    severity="medium",
                ),
                text,
            )
        if profile.latin == 0:
            return None  # Arabic-only (or no letters): never leaves the server.

        # 6. length
        v = length_guard.check(clean, int(settings.english_char_limit or 0))
        if v:
            return self._with_excerpt(v, text)

        latin_text = profile.latin_text.strip()
        if lang.latin_letter_count(latin_text) < 2:
            return None
        enabled = set(settings.moderation_categories or [])

        # 7. local wordlist
        v = wordlist.check(latin_text, enabled)
        if v:
            return self._with_excerpt(v, text)

        # 8. moderation API (Latin segments only)
        if not settings.english_moderation:
            return None
        try:
            result = await self.ctx.moderation.classify(s, latin_text, sorted(enabled))
        except ModerationUnavailable as e:
            mode = settings.api_fail_mode
            if mode == "default":
                mode = self.ctx.config.moderation_fail_mode
            await self.ctx.notifier.api_failure(s, ch, str(e))
            if mode == "closed":
                return self._with_excerpt(
                    Verdict(
                        kind=KIND_CONTENT,
                        rule="moderation:unavailable_fail_closed",
                        detail=str(e)[:120],
                        severity="low",
                        api_result={"error": str(e)[:200]},
                    ),
                    text,
                )
            return None

        if result.flagged:
            return self._with_excerpt(
                Verdict(
                    kind=KIND_CONTENT,
                    rule=f"moderation:{result.category}",
                    detail=result.reason or result.category,
                    severity=result.severity,
                    api_result=result.as_dict(),
                ),
                text,
            )
        if settings.foreign_latin_violation and result.language and result.language not in ("en", "und", ""):
            if profile.latin >= 12:
                return self._with_excerpt(
                    Verdict(
                        kind=KIND_LANGUAGE,
                        rule=f"language_guard:latin_{result.language}",
                        detail=result.language,
                        severity="low",
                        api_result=result.as_dict(),
                    ),
                    text,
                )
        return None

    @staticmethod
    def _with_excerpt(v: Verdict, text: str) -> Verdict:
        v.excerpt = excerpt(text)
        return v
