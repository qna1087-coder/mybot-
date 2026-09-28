"""Promote, demote (with a precise rights snapshot), restore, and adopt administrators."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.errors import AdminNotManaged, BotRightsMissing, TelegramFailure
from vigil.core.retry import is_rights_error, short_error, tg
from vigil.core.rights import (
    ADMIN_RIGHT_FIELDS,
    NO_RIGHTS,
    intersect_with_bot,
    normalize_rights,
    rights_from_member,
)
from vigil.core.timeutil import utcnow
from vigil.db.models import Admin, AdminSnapshot, Channel
from vigil.db.repo import admins as repo
from vigil.db.repo import audit
from vigil.db.repo import snapshots as snap_repo
from vigil.services.context import Services

log = logging.getLogger("vigil.admins")


@dataclass
class RestoreOutcome:
    ok: bool
    dropped_rights: list[str] = field(default_factory=list)
    error: str | None = None
    custom_title: str | None = None


class AdminService:
    def __init__(self, ctx: Services):
        self.ctx = ctx

    # ── Telegram primitives ──────────────────────────────────

    async def _promote(self, channel_id: int, user_id: int, rights: dict[str, bool]) -> None:
        kwargs = {f: bool(rights.get(f, False)) for f in ADMIN_RIGHT_FIELDS}
        await tg(lambda: self.ctx.bot.promote_chat_member(channel_id, user_id, **kwargs), label="promoteChatMember")

    async def fetch_member(self, channel_id: int, user_id: int) -> Any | None:
        try:
            return await tg(lambda: self.ctx.bot.get_chat_member(channel_id, user_id), label="getChatMember")
        except TelegramAPIError as e:
            log.info("getChatMember failed %s/%s: %s", channel_id, user_id, short_error(e))
            return None

    def _require_bot_rights(self, ch: Channel, *needed: str) -> None:
        rights = ch.bot_rights or {}
        missing = [r for r in needed if not rights.get(r)]
        if missing:
            raise BotRightsMissing(missing)

    # ── promote / add ────────────────────────────────────────

    async def promote(
        self,
        s: AsyncSession,
        ch: Channel,
        user_id: int,
        rights: dict[str, bool],
        *,
        by: int | None,
        username: str | None = None,
        full_name: str = "",
    ) -> tuple[Admin, list[str]]:
        self._require_bot_rights(ch, "can_promote_members")
        grant, dropped = intersect_with_bot(normalize_rights(rights), ch.bot_rights)
        try:
            await self._promote(ch.id, user_id, grant)
        except TelegramAPIError as e:
            if is_rights_error(e):
                raise AdminNotManaged(short_error(e)) from e
            raise TelegramFailure(short_error(e)) from e

        member = await self.fetch_member(ch.id, user_id)
        if member is not None and isinstance(member, ChatMemberAdministrator):
            grant = rights_from_member(member)
            username = member.user.username
            full_name = " ".join(p for p in (member.user.first_name, member.user.last_name) if p)
        admin = await repo.upsert(
            s,
            ch.id,
            user_id,
            username=username,
            full_name=full_name,
            status="active",
            managed_by_bot=True,
            rights=grant,
            promoted_at=utcnow(),
            demoted_at=None,
            demote_reason=None,
        )
        await audit.log(
            s, "admin.promoted", channel_id=ch.id, actor=by, target_type="user", target_id=user_id,
            rights=[k for k, v in grant.items() if v], dropped=dropped,
        )
        return admin, dropped

    # ── demote with snapshot ─────────────────────────────────

    async def demote(
        self,
        s: AsyncSession,
        ch: Channel,
        admin: Admin,
        *,
        reason: str,
        snapshot_reason: str,
        new_status: str = "suspended",
        by: int | None = None,
    ) -> AdminSnapshot:
        """Snapshot first, then demote. Raises AdminNotManaged when Telegram refuses."""
        if admin.status == "owner":
            raise AdminNotManaged("owner")
        self._require_bot_rights(ch, "can_promote_members")

        rights = normalize_rights(admin.rights)
        custom_title = admin.custom_title
        member = await self.fetch_member(ch.id, admin.user_id)
        if isinstance(member, ChatMemberOwner):
            raise AdminNotManaged("owner")
        if isinstance(member, ChatMemberAdministrator):
            rights = rights_from_member(member)
            custom_title = member.custom_title
            if not member.can_be_edited:
                admin.managed_by_bot = False
                admin.status = "unmanaged"
                await s.flush()
                raise AdminNotManaged("promoted outside Vigil")

        snap = await snap_repo.create(
            s,
            channel_id=ch.id,
            user_id=admin.user_id,
            admin_id=admin.id,
            rights=rights,
            custom_title=custom_title,
            reason=snapshot_reason,
        )
        try:
            await self._promote(ch.id, admin.user_id, dict(NO_RIGHTS))
        except TelegramAPIError as e:
            await snap_repo.mark_failed(s, snap, f"demote: {short_error(e)}")
            if is_rights_error(e):
                admin.managed_by_bot = False
                admin.status = "unmanaged"
                await s.flush()
                raise AdminNotManaged(short_error(e)) from e
            raise TelegramFailure(short_error(e)) from e

        admin.rights = rights
        admin.custom_title = custom_title
        admin.status = new_status
        admin.demoted_at = utcnow()
        admin.demote_reason = reason[:255]
        await s.flush()
        await audit.log(
            s, "admin.demoted", channel_id=ch.id, actor=by, target_type="user", target_id=admin.user_id,
            reason=reason, snapshot_id=snap.id, mode=snapshot_reason,
        )
        return snap

    # ── restore ──────────────────────────────────────────────

    async def restore(
        self,
        s: AsyncSession,
        ch: Channel,
        user_id: int,
        snap: AdminSnapshot | None,
        *,
        by: int | None,
        source: str = "manual",
    ) -> RestoreOutcome:
        self._require_bot_rights(ch, "can_promote_members")
        admin = await repo.get_by_user(s, ch.id, user_id)
        rights = normalize_rights(snap.rights if snap else (admin.rights if admin else None))
        if not any(v for k, v in rights.items() if k != "is_anonymous"):
            from vigil.core.rights import PRESETS

            rights = dict(PRESETS["publisher"])
        grant, dropped = intersect_with_bot(rights, ch.bot_rights)
        try:
            await self._promote(ch.id, user_id, grant)
        except TelegramAPIError as e:
            err = short_error(e)
            if snap is not None:
                await snap_repo.mark_failed(s, snap, err)
            await audit.log(
                s, "admin.restore_failed", channel_id=ch.id, actor=by, target_type="user", target_id=user_id,
                error=err, source=source,
            )
            return RestoreOutcome(ok=False, error=err)

        if snap is not None:
            await snap_repo.mark_restored(s, snap, by)
        if admin is not None:
            admin.status = "active"
            admin.managed_by_bot = True
            admin.rights = grant
            admin.promoted_at = utcnow()
            admin.demoted_at = None
            admin.demote_reason = None
        await s.flush()
        await audit.log(
            s, "admin.restored", channel_id=ch.id, actor=by, target_type="user", target_id=user_id,
            dropped=dropped, source=source, snapshot_id=snap.id if snap else None,
        )
        return RestoreOutcome(ok=True, dropped_rights=dropped, custom_title=snap.custom_title if snap else None)

    # ── removal / misc ───────────────────────────────────────

    async def remove(self, s: AsyncSession, ch: Channel, admin: Admin, *, by: int | None) -> None:
        if admin.status in ("suspended", "shielded"):
            admin.status = "removed"
            await s.flush()
            await audit.log(s, "admin.removed", channel_id=ch.id, actor=by, target_type="user", target_id=admin.user_id)
            return
        await self.demote(s, ch, admin, reason="removed by manager", snapshot_reason="manual", new_status="removed", by=by)
        await audit.log(s, "admin.removed", channel_id=ch.id, actor=by, target_type="user", target_id=admin.user_id)

    async def set_exempt(self, s: AsyncSession, ch: Channel, admin: Admin, exempt: bool, *, by: int | None) -> None:
        admin.shield_exempt = exempt
        await s.flush()
        await audit.log(
            s, "admin.shield_exempt", channel_id=ch.id, actor=by, target_type="user", target_id=admin.user_id, exempt=exempt
        )

    async def reset_status(self, s: AsyncSession, ch: Channel, admin: Admin, *, by: int | None) -> None:
        admin.violations_count = 0
        admin.last_violation_id = None
        admin.demote_reason = None
        if admin.status in ("suspended",) and admin.managed_by_bot is False:
            admin.status = "unmanaged"
        await s.flush()
        await audit.log(s, "admin.reset", channel_id=ch.id, actor=by, target_type="user", target_id=admin.user_id)

    async def refresh_bot_rights(self, s: AsyncSession, ch: Channel) -> dict[str, bool] | None:
        member = await self.fetch_member(ch.id, self.ctx.bot_id)
        if isinstance(member, ChatMemberAdministrator):
            ch.bot_rights = rights_from_member(member)
            ch.bot_status = "administrator"
        elif member is not None:
            ch.bot_rights = None
            ch.bot_status = getattr(member, "status", "unknown")
        await s.flush()
        return ch.bot_rights
