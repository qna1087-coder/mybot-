from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.timeutil import utcnow
from vigil.db.models import Violation


async def get(s: AsyncSession, violation_id: int) -> Violation | None:
    return await s.get(Violation, violation_id)


async def find(s: AsyncSession, channel_id: int, message_id: int, rule: str) -> Violation | None:
    res = await s.execute(
        select(Violation).where(
            Violation.channel_id == channel_id, Violation.message_id == message_id, Violation.rule == rule
        )
    )
    return res.scalar_one_or_none()


async def create(s: AsyncSession, **fields: Any) -> Violation:
    v = Violation(**fields)
    s.add(v)
    await s.flush()
    return v


async def list_for_channel(s: AsyncSession, channel_id: int, *, limit: int = 10, offset: int = 0) -> list[Violation]:
    res = await s.execute(
        select(Violation)
        .where(Violation.channel_id == channel_id)
        .order_by(Violation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(res.scalars())


async def list_for_admin(s: AsyncSession, channel_id: int, user_id: int, *, limit: int = 5) -> list[Violation]:
    res = await s.execute(
        select(Violation)
        .where(Violation.channel_id == channel_id, Violation.user_id == user_id)
        .order_by(Violation.created_at.desc())
        .limit(limit)
    )
    return list(res.scalars())


async def count_for_channel(s: AsyncSession, channel_id: int) -> int:
    res = await s.execute(select(func.count()).select_from(Violation).where(Violation.channel_id == channel_id))
    return int(res.scalar_one())


async def mark_restored(s: AsyncSession, v: Violation, by: int | None) -> None:
    v.restored_at = utcnow()
    v.restored_by = by
    await s.flush()
