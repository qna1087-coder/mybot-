from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.timeutil import utcnow
from vigil.db.models import ShieldMember, ShieldSchedule, ShieldSession

# ── schedules ──────────────────────────────────────────────────

async def list_schedules(s: AsyncSession, channel_id: int) -> list[ShieldSchedule]:
    res = await s.execute(
        select(ShieldSchedule).where(ShieldSchedule.channel_id == channel_id).order_by(ShieldSchedule.start_time)
    )
    return list(res.scalars())


async def list_enabled_schedules(s: AsyncSession) -> list[ShieldSchedule]:
    res = await s.execute(select(ShieldSchedule).where(ShieldSchedule.enabled.is_(True)))
    return list(res.scalars())


async def get_schedule(s: AsyncSession, schedule_id: int) -> ShieldSchedule | None:
    return await s.get(ShieldSchedule, schedule_id)


async def create_schedule(s: AsyncSession, **fields: Any) -> ShieldSchedule:
    sched = ShieldSchedule(**fields)
    s.add(sched)
    await s.flush()
    return sched


async def delete_schedule(s: AsyncSession, sched: ShieldSchedule) -> None:
    await s.delete(sched)
    await s.flush()


# ── sessions ───────────────────────────────────────────────────

async def active_session(s: AsyncSession, channel_id: int) -> ShieldSession | None:
    res = await s.execute(
        select(ShieldSession)
        .where(ShieldSession.channel_id == channel_id, ShieldSession.status.in_(("active", "ending")))
        .order_by(ShieldSession.started_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def list_active_sessions(s: AsyncSession) -> list[ShieldSession]:
    res = await s.execute(select(ShieldSession).where(ShieldSession.status.in_(("active", "ending"))))
    return list(res.scalars())


async def get_session(s: AsyncSession, session_id: int) -> ShieldSession | None:
    return await s.get(ShieldSession, session_id)


async def create_session(s: AsyncSession, **fields: Any) -> ShieldSession:
    sess = ShieldSession(**fields)
    s.add(sess)
    await s.flush()
    return sess


async def list_recent_sessions(s: AsyncSession, channel_id: int, limit: int = 5) -> list[ShieldSession]:
    res = await s.execute(
        select(ShieldSession)
        .where(ShieldSession.channel_id == channel_id)
        .order_by(ShieldSession.started_at.desc())
        .limit(limit)
    )
    return list(res.scalars())


async def finish_session(s: AsyncSession, sess: ShieldSession, status: str, note: str | None = None) -> None:
    sess.status = status
    sess.ended_at = utcnow()
    if note:
        sess.note = note[:255]
    await s.flush()


# ── members ────────────────────────────────────────────────────

async def add_member(s: AsyncSession, **fields: Any) -> ShieldMember:
    m = ShieldMember(**fields)
    s.add(m)
    await s.flush()
    return m


async def list_members(s: AsyncSession, session_id: int) -> list[ShieldMember]:
    res = await s.execute(select(ShieldMember).where(ShieldMember.session_id == session_id).order_by(ShieldMember.id))
    return list(res.scalars())


async def list_unrestored_members(s: AsyncSession, session_id: int) -> list[ShieldMember]:
    res = await s.execute(
        select(ShieldMember).where(
            ShieldMember.session_id == session_id, ShieldMember.status.in_(("suspended", "failed"))
        )
    )
    return list(res.scalars())


async def list_failed_restores(s: AsyncSession, max_attempts: int = 30) -> list[ShieldMember]:
    """Members of finished sessions that still need a restore."""
    res = await s.execute(
        select(ShieldMember)
        .join(ShieldSession, ShieldSession.id == ShieldMember.session_id)
        .where(
            ShieldSession.status.in_(("ended", "failed")),
            ShieldMember.status == "failed",
            ShieldMember.attempts < max_attempts,
        )
    )
    return list(res.scalars())


async def member_by_user(s: AsyncSession, session_id: int, user_id: int) -> ShieldMember | None:
    res = await s.execute(
        select(ShieldMember).where(ShieldMember.session_id == session_id, ShieldMember.user_id == user_id)
    )
    return res.scalar_one_or_none()
