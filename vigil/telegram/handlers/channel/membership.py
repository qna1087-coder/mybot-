"""Bot added / removed / rights changed, and administrator changes made by humans."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner, ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.rights import rights_from_member
from vigil.core.timeutil import utcnow
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import audit
from vigil.db.repo import channels as ch_repo
from vigil.db.repo import shield as shield_repo
from vigil.db.repo import users as user_repo
from vigil.services.context import Services

log = logging.getLogger("vigil.membership")
router = Router(name="channel_membership")

ADMIN_STATUSES = ("administrator", "creator")


def _name(u) -> str:  # noqa: ANN001
    return " ".join(p for p in (u.first_name, u.last_name) if p) or (f"@{u.username}" if u.username else str(u.id))


@router.my_chat_member(F.chat.type == "channel")
async def on_my_chat_member(event: ChatMemberUpdated, ctx: Services, s: AsyncSession) -> None:
    new, old = event.new_chat_member, event.old_chat_member
    actor = event.from_user
    chat = event.chat

    if new.status == "administrator":
        ch = await ch_repo.get(s, chat.id)
        was_present = old.status in ADMIN_STATUSES
        if ch is None or ch.status in ("pending", "detached", "revoked"):
            prev_status = ch.status if ch else None
            ch, is_new = await ctx.channels.register_pending(s, chat, added_by=actor.id if actor else None, bot_member=new)
            if actor is not None and not actor.is_bot:
                await user_repo.ensure(s, actor.id, username=actor.username, first_name=actor.first_name, last_name=actor.last_name)
            if ch.status == "active" and prev_status == "detached":
                await ctx.channels.sync_admins(s, ch)
                await ctx.notifier.reattached(s, ch)
                return
            if ch.status == "pending" and (is_new or not was_present):
                owner_name = "?"
                sync = await ctx.channels.sync_admins(s, ch)
                if sync.owner_user_id:
                    ch.owner_user_id = sync.owner_user_id
                    for a in sync.admins:
                        if a.user_id == sync.owner_user_id:
                            owner_name = a.display
                await ctx.notifier.channel_pending(s, ch, _name(actor) if actor else "?", owner_name)
                await ctx.notifier.unauthorized_notice(s, ch, actor.id if actor else None)
            return

        # active / suspended: rights update
        before = set(ctx.channels.missing_bot_rights(ch))
        await ctx.channels.update_bot_rights(s, chat.id, new)
        after = set(ctx.channels.missing_bot_rights(ch))
        if isinstance(old, ChatMemberAdministrator) and rights_from_member(old) != rights_from_member(new):
            await audit.log(s, "channel.bot_rights_changed", channel_id=ch.id, actor=actor.id if actor else None, missing=sorted(after))
        if after and after != before:
            await ctx.notifier.bot_rights_alert(s, ch, sorted(after))
        if not was_present:
            await ctx.channels.sync_admins(s, ch)
        return

    if new.status in ("left", "kicked", "member", "restricted"):
        ch = await ch_repo.get(s, chat.id)
        if ch is None:
            return
        shield_members = 0
        sess = await shield_repo.active_session(s, ch.id)
        if sess is not None:
            shield_members = sum(1 for m in await shield_repo.list_members(s, sess.id) if m.status == "suspended")
        await ctx.channels.detach(s, chat.id, status_now=new.status)
        await ctx.notifier.bot_removed(s, ch, shield_members=shield_members)


@router.chat_member(F.chat.type == "channel")
async def on_chat_member(event: ChatMemberUpdated, ctx: Services, s: AsyncSession) -> None:
    ch = await ch_repo.get(s, event.chat.id)
    if ch is None or ch.status not in ("active", "suspended"):
        return
    actor = event.from_user
    if actor is not None and actor.id == ctx.bot_id:
        return  # our own promotions/demotions are recorded by the services
    new, old = event.new_chat_member, event.old_chat_member
    user = new.user
    if user.is_bot:
        return
    existing = await admin_repo.get_by_user(s, ch.id, user.id)

    if isinstance(new, ChatMemberOwner):
        await admin_repo.upsert(
            s, ch.id, user.id, username=user.username, full_name=_name(user), custom_title=new.custom_title,
            status="owner", managed_by_bot=False, rights=rights_from_member(new),
        )
        ch.owner_user_id = user.id
        return

    if isinstance(new, ChatMemberAdministrator):
        manageable = bool(new.can_be_edited)
        prev = existing.status if existing else None
        admin = await admin_repo.upsert(
            s, ch.id, user.id, username=user.username, full_name=_name(user), custom_title=new.custom_title,
            status="active" if manageable else "unmanaged", managed_by_bot=manageable, rights=rights_from_member(new),
            promoted_at=(existing.promoted_at if existing and existing.promoted_at else utcnow()),
        )
        if old.status not in ADMIN_STATUSES:
            await audit.log(
                s, "admin.promoted", channel_id=ch.id, actor=actor.id if actor else None, target_type="user",
                target_id=user.id, external=True, managed=manageable,
            )
            if prev in ("suspended", "shielded"):
                await audit.log(s, "admin.repromoted_externally", channel_id=ch.id, actor=actor.id if actor else None, target_type="user", target_id=user.id, previous=prev)
                await ctx.notifier.external_repromote(s, ch, admin)
        return

    if old.status in ADMIN_STATUSES and new.status not in ADMIN_STATUSES:
        if existing is not None and existing.status in ("active", "unmanaged", "owner"):
            existing.status = "removed"
            existing.demoted_at = utcnow()
            existing.demote_reason = "removed in Telegram"
            await s.flush()
            await audit.log(s, "admin.removed_externally", channel_id=ch.id, actor=actor.id if actor else None, target_type="user", target_id=user.id)
