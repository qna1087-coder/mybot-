"""Every channel post (and edit) passes through here."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.repo import audit
from vigil.db.repo import channels as ch_repo
from vigil.services.context import Services

log = logging.getLogger("vigil.posts")
router = Router(name="channel_posts")


@router.channel_post(F.chat.type == "channel")
@router.edited_channel_post(F.chat.type == "channel")
async def on_channel_post(message: Message, ctx: Services, s: AsyncSession) -> None:
    ch = await ch_repo.get(s, message.chat.id)
    if ch is None or not ch.is_active:
        return
    if ch.title != (message.chat.title or ch.title):
        ch.title = message.chat.title or ch.title
    settings = await ctx.settings.get(s, ch.id)
    if not settings.guard_enabled:
        return

    attribution = await ctx.attributor.attribute(s, ch, message)
    if attribution.status in ("self", "owner"):
        return

    if attribution.status == "unsigned" and settings.unattributed_alerts:
        await ctx.notifier.unattributed(s, ch)
    elif attribution.status == "ambiguous" and attribution.candidates:
        await audit.log(s, "post.ambiguous", channel_id=ch.id, signature=attribution.signature, message_id=message.message_id)
        await ctx.notifier.ambiguous(s, ch, attribution.signature or "", attribution.candidates)
    elif attribution.status == "unknown":
        await audit.log(s, "post.unattributed", channel_id=ch.id, signature=attribution.signature, message_id=message.message_id)

    verdict = await ctx.guard.evaluate(s, ch, message, settings)
    if verdict is None:
        return
    log.info("violation in %s msg %s: %s (%s)", ch.id, message.message_id, verdict.rule, attribution.status)
    await ctx.enforcer.apply(s, ch, message, verdict, attribution, settings)
