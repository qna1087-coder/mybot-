"""Shield Mode sessions: suspend managed administrators, remember everything, restore precisely."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.errors import AdminNotManaged, BotRightsMissing, TelegramFailure
from vigil.core.timeutil import utcnow
from vigil.db.models import Admin, Channel, ShieldMember, ShieldSession
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import audit
from vigil.db.repo import channels as ch_repo
from vigil.db.repo import shield as repo
from vigil.db.repo import snapshots as snap_repo
from vigil.services.context import Services
from vigil.services.shield.schedules import next_window

log = logging.getLogger("vigil.shield")


@dataclass
class StartOutcome:
    session: ShieldSession
    suspended: list[Admin] = field(default_factory=list)
    skipped: list[tuple[Admin, str]] = field(default_factory=list)


@dataclass
class EndOutcome:
    session: ShieldSession
    restored: list[ShieldMember] = field(default_factory=list)
    failed: list[tuple[ShieldMember, str]] = field(default_factory=list)


@dataclass
class ShieldStatus:
    session: ShieldSession | None
    suspended: int = 0
    failed: int = 0
    exempt: int = 0
    schedules: int = 0
    next_start: datetime | None = None
    next_end: datetime | None = None


class ShieldService:
    def __init__(self, ctx: Services):
        self.ctx = ctx
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, channel_id: int) -> asyncio.Lock:
        return self._locks.setdefault(channel_id, asyncio.Lock())

    # ── status ───────────────────────────────────────────────

    async def status(self, s: AsyncSession, ch: Channel) -> ShieldStatus:
        sess = await repo.active_session(s, ch.id)
        st = ShieldStatus(session=sess)
        if sess is not None:
            members = await repo.list_members(s, sess.id)
            st.suspended = sum(1 for m in members if m.status == "suspended")
            st.failed = sum(1 for m in members if m.status == "failed")
        counts = await admin_repo.list_for_channel(s, ch.id, statuses=("active",))
        st.exempt = sum(1 for a in counts if a.shield_exempt)
        schedules = [x for x in await repo.list_schedules(s, ch.id) if x.enabled]
        st.schedules = len(schedules)
        now = utcnow()
        best: tuple[datetime, datetime] | None = None
        for sched in schedules:
            win = next_window(sched, now)
            if win and (best is None or win[0] < best[0]):
                best = win
        if best:
            st.next_start, st.next_end = best
        return st

    # ── start ────────────────────────────────────────────────

    async def start(
        self,
        s: AsyncSession,
        ch: Channel,
        *,
        by: int | None,
        trigger: str = "manual",
        ends_at: datetime | None = None,
        schedule_id: int | None = None,
        notify: bool = True,
    ) -> StartOutcome | None:
        async with self._lock(ch.id):
            if await repo.active_session(s, ch.id) is not None:
                return None
            missing = self.ctx.channels.missing_bot_rights(ch)
            if "can_promote_members" in missing:
                raise BotRightsMissing(missing)

            sess = await repo.create_session(
                s, channel_id=ch.id, trigger=trigger, schedule_id=schedule_id, started_by=by, ends_at=ends_at
            )
            outcome = StartOutcome(session=sess)
            for admin in await admin_repo.list_shieldable(s, ch.id):
                try:
                    snap = await self.ctx.admins.demote(
                        s, ch, admin, reason="Shield Mode", snapshot_reason="shield", new_status="shielded", by=by
                    )
                except AdminNotManaged as e:
                    outcome.skipped.append((admin, str(e)))
                    await repo.add_member(
                        s, session_id=sess.id, channel_id=ch.id, user_id=admin.user_id, admin_id=admin.id,
                        status="skipped", error=str(e)[:255],
                    )
                    continue
                except TelegramFailure as e:
                    outcome.skipped.append((admin, str(e)))
                    await repo.add_member(
                        s, session_id=sess.id, channel_id=ch.id, user_id=admin.user_id, admin_id=admin.id,
                        status="skipped", error=str(e)[:255],
                    )
                    continue
                await repo.add_member(
                    s, session_id=sess.id, channel_id=ch.id, user_id=admin.user_id, admin_id=admin.id,
                    snapshot_id=snap.id, status="suspended",
                )
                outcome.suspended.append(admin)
                await asyncio.sleep(0.15)  # be gentle with Telegram

            await audit.log(
                s, "shield.on", channel_id=ch.id, actor=by, target_type="session", target_id=sess.id,
                trigger=trigger, suspended=len(outcome.suspended), skipped=len(outcome.skipped),
                ends_at=ends_at.isoformat() if ends_at else None,
            )
            if notify:
                await self.ctx.notifier.shield_started(s, ch, outcome)
            return outcome

    # ── end ──────────────────────────────────────────────────

    async def end(
        self, s: AsyncSession, sess: ShieldSession, *, by: int | None = None, reason: str = "manual", notify: bool = True
    ) -> EndOutcome:
        async with self._lock(sess.channel_id):
            ch = await ch_repo.get(s, sess.channel_id)
            outcome = EndOutcome(session=sess)
            sess.status = "ending"
            await s.flush()
            for member in await repo.list_unrestored_members(s, sess.id):
                ok, err = await self._restore_member(s, ch, member, by=by)
                if ok:
                    outcome.restored.append(member)
                else:
                    outcome.failed.append((member, err or "unknown"))
                await asyncio.sleep(0.15)
            await repo.finish_session(s, sess, "ended" if not outcome.failed else "failed", note=reason)
            await audit.log(
                s, "shield.off", channel_id=sess.channel_id, actor=by, target_type="session", target_id=sess.id,
                reason=reason, restored=len(outcome.restored), failed=len(outcome.failed),
            )
            if notify and ch is not None:
                await self.ctx.notifier.shield_ended(s, ch, outcome)
            return outcome

    async def _restore_member(
        self, s: AsyncSession, ch: Channel | None, member: ShieldMember, *, by: int | None
    ) -> tuple[bool, str | None]:
        member.attempts += 1
        if ch is None or ch.status == "detached" or not (ch.bot_rights or {}).get("can_promote_members"):
            member.status = "failed"
            member.error = "bot has no rights in channel"
            await s.flush()
            return False, member.error
        snap = await snap_repo.get(s, member.snapshot_id) if member.snapshot_id else None
        try:
            outcome = await self.ctx.admins.restore(s, ch, member.user_id, snap, by=by, source="shield")
        except BotRightsMissing as e:
            member.status = "failed"
            member.error = f"bot rights: {e}"
            await s.flush()
            return False, member.error
        if outcome.ok:
            member.status = "restored"
            member.error = None
            member.restored_at = utcnow()
            await s.flush()
            return True, None
        member.status = "failed"
        member.error = (outcome.error or "unknown")[:255]
        await s.flush()
        await audit.log(
            s, "shield.member_failed", channel_id=member.channel_id, target_type="user", target_id=member.user_id,
            error=member.error, attempts=member.attempts,
        )
        return False, member.error

    # ── retries ──────────────────────────────────────────────

    async def retry_failed(self, s: AsyncSession, *, only_fast: bool) -> int:
        """Retry failed restores of finished sessions. Returns number restored."""
        restored = 0
        for member in await repo.list_failed_restores(s):
            if only_fast and member.attempts >= 10:
                continue
            ch = await ch_repo.get(s, member.channel_id)
            ok, _ = await self._restore_member(s, ch, member, by=None)
            if ok:
                restored += 1
                sess = await repo.get_session(s, member.session_id)
                if sess is not None and not await repo.list_unrestored_members(s, sess.id):
                    sess.status = "ended"
                    await s.flush()
                if ch is not None:
                    await self.ctx.notifier.shield_member_restored(s, ch, member)
            await asyncio.sleep(0.2)
        return restored

    async def retry_session(self, s: AsyncSession, sess: ShieldSession, *, by: int | None) -> EndOutcome:
        ch = await ch_repo.get(s, sess.channel_id)
        outcome = EndOutcome(session=sess)
        for member in await repo.list_unrestored_members(s, sess.id):
            ok, err = await self._restore_member(s, ch, member, by=by)
            if ok:
                outcome.restored.append(member)
            else:
                outcome.failed.append((member, err or "unknown"))
            await asyncio.sleep(0.15)
        if not await repo.list_unrestored_members(s, sess.id):
            sess.status = "ended"
            await s.flush()
        return outcome
