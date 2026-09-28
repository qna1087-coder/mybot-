"""Channel lifecycle: pending → active → suspended / revoked / detached, plus admin sync."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aiogram.exceptions import TelegramAPIError
from aiogram.types import Chat, ChatMemberAdministrator, ChatMemberOwner
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.retry import short_error, tg
from vigil.core.rights import REQUIRED_BOT_RIGHTS, rights_from_member
from vigil.core.timeutil import utcnow
from vigil.db.models import Admin, Channel
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import audit
from vigil.db.repo import channels as repo
from vigil.db.repo import permissions as perm_repo
from vigil.db.repo import users as user_repo
from vigil.services.context import Services

log = logging.getLogger("vigil.channels")


@dataclass
class SyncResult:
    admins: list[Admin] = field(default_factory=list)
    owner_user_id: int | None = None
    bot_rights: dict[str, bool] | None = None
    removed: list[Admin] = field(default_factory=list)
    error: str | None = None


class ChannelService:
    def __init__(self, ctx: Services):
        self.ctx = ctx

    # ── registration ─────────────────────────────────────────

    async def register_pending(
        self, s: AsyncSession, chat: Chat, *, added_by: int | None, bot_member: Any
    ) -> tuple[Channel, bool]:
        """Bot was added to a channel. Returns (channel, is_new)."""
        existing = await repo.get(s, chat.id)
        rights = rights_from_member(bot_member) if isinstance(bot_member, ChatMemberAdministrator) else None
        status_now = getattr(bot_member, "status", "unknown")
        if existing is None:
            ch = await repo.upsert(
                s,
                chat.id,
                title=chat.title or "",
                username=chat.username,
                status="pending",
                added_by=added_by,
                timezone=self.ctx.config.default_timezone,
                bot_rights=rights,
                bot_status=status_now,
            )
            await audit.log(s, "channel.unauthorized_attempt", channel_id=chat.id, actor=added_by, title=chat.title)
            return ch, True
        existing.title = chat.title or existing.title
        existing.username = chat.username
        existing.bot_rights = rights
        existing.bot_status = status_now
        if existing.status == "detached":
            existing.status = "active" if existing.authorized_at else "pending"
            await audit.log(s, "channel.reattached", channel_id=chat.id, actor=added_by)
        elif existing.status == "pending":
            await audit.log(s, "channel.unauthorized_attempt", channel_id=chat.id, actor=added_by, title=chat.title)
        await s.flush()
        return existing, False

    async def activate(self, s: AsyncSession, channel_id: int, *, by: int) -> tuple[Channel, SyncResult]:
        ch = await repo.get(s, channel_id)
        if ch is None:
            raise LookupError(channel_id)
        ch.status = "active"
        ch.authorized_by = by
        ch.authorized_at = utcnow()
        sync = await self.sync_admins(s, ch)
        owner_id = sync.owner_user_id
        if owner_id:
            ch.owner_user_id = owner_id
            await user_repo.ensure(s, owner_id)
            await perm_repo.grant(s, channel_id, owner_id, "owner", by)
        if ch.added_by and ch.added_by != owner_id:
            await user_repo.ensure(s, ch.added_by)
            await perm_repo.grant(s, channel_id, ch.added_by, "manager", by)
        await audit.log(s, "channel.activated", channel_id=channel_id, actor=by, owner=owner_id)
        await s.flush()
        return ch, sync

    async def set_status(self, s: AsyncSession, channel_id: int, status: str, *, by: int | None, action: str) -> Channel:
        ch = await repo.get(s, channel_id)
        if ch is None:
            raise LookupError(channel_id)
        ch.status = status
        await audit.log(s, action, channel_id=channel_id, actor=by)
        await s.flush()
        return ch

    async def detach(self, s: AsyncSession, channel_id: int, *, status_now: str) -> Channel | None:
        ch = await repo.get(s, channel_id)
        if ch is None:
            return None
        ch.bot_status = status_now
        if ch.status in ("active", "pending", "suspended"):
            ch.status = "detached"
        ch.bot_rights = None
        await audit.log(s, "channel.bot_removed", channel_id=channel_id, status=status_now)
        await s.flush()
        return ch

    async def update_bot_rights(self, s: AsyncSession, channel_id: int, member: Any) -> Channel | None:
        ch = await repo.get(s, channel_id)
        if ch is None:
            return None
        if isinstance(member, ChatMemberAdministrator):
            ch.bot_rights = rights_from_member(member)
            ch.bot_status = "administrator"
        else:
            ch.bot_rights = None
            ch.bot_status = getattr(member, "status", "unknown")
        await s.flush()
        return ch

    # ── sync ─────────────────────────────────────────────────

    async def sync_admins(self, s: AsyncSession, ch: Channel) -> SyncResult:
        """Mirror Telegram's administrator list into our registry."""
        result = SyncResult()
        try:
            members = await tg(lambda: self.ctx.bot.get_chat_administrators(ch.id), label="getChatAdministrators")
        except TelegramAPIError as e:
            result.error = short_error(e)
            log.warning("sync failed for %s: %s", ch.id, result.error)
            return result

        keep: set[int] = set()
        for m in members:
            user = m.user
            if user.id == self.ctx.bot_id:
                if isinstance(m, ChatMemberAdministrator):
                    result.bot_rights = rights_from_member(m)
                    ch.bot_rights = result.bot_rights
                    ch.bot_status = "administrator"
                continue
            if user.is_bot:
                continue
            keep.add(user.id)
            full_name = " ".join(p for p in (user.first_name, user.last_name) if p)
            if isinstance(m, ChatMemberOwner):
                result.owner_user_id = user.id
                admin = await admin_repo.upsert(
                    s,
                    ch.id,
                    user.id,
                    username=user.username,
                    full_name=full_name,
                    custom_title=m.custom_title,
                    status="owner",
                    managed_by_bot=False,
                    rights=rights_from_member(m),
                )
                result.admins.append(admin)
                continue
            if isinstance(m, ChatMemberAdministrator):
                existing = await admin_repo.get_by_user(s, ch.id, user.id)
                manageable = bool(m.can_be_edited)
                status = "active" if manageable else "unmanaged"
                fields: dict[str, Any] = {
                    "username": user.username,
                    "full_name": full_name,
                    "custom_title": m.custom_title,
                    "managed_by_bot": manageable,
                    "rights": rights_from_member(m),
                    "status": status,
                }
                if existing is None or existing.promoted_at is None:
                    fields["promoted_at"] = utcnow()
                if existing is not None and existing.status in ("suspended", "shielded"):
                    # Someone re-promoted this admin outside Vigil while we held them down.
                    await audit.log(
                        s,
                        "admin.repromoted_externally",
                        channel_id=ch.id,
                        target_type="user",
                        target_id=user.id,
                        previous=existing.status,
                    )
                admin = await admin_repo.upsert(s, ch.id, user.id, **fields)
                result.admins.append(admin)

        result.removed = await admin_repo.mark_removed_except(s, ch.id, keep)
        for a in result.removed:
            await audit.log(s, "admin.removed_externally", channel_id=ch.id, target_type="user", target_id=a.user_id)
        if result.owner_user_id and ch.owner_user_id != result.owner_user_id:
            ch.owner_user_id = result.owner_user_id
        await s.flush()
        return result

    # ── helpers ──────────────────────────────────────────────

    def missing_bot_rights(self, ch: Channel) -> list[str]:
        rights = ch.bot_rights or {}
        return [r for r in REQUIRED_BOT_RIGHTS if not rights.get(r)]

    async def signature_registry(self, s: AsyncSession, channel_id: int) -> dict[str, list[Admin]]:
        """signature → admins. Custom title wins over the name (that is what Telegram shows)."""
        registry: dict[str, list[Admin]] = {}
        for a in await admin_repo.list_for_channel(s, channel_id, statuses=("active", "owner", "unmanaged")):
            keys = {a.signature_key}
            if a.full_name:
                keys.add(a.full_name.strip())
            for k in keys:
                if k:
                    registry.setdefault(k, []).append(a)
        return registry
