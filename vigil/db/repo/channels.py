from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.models import Channel, ChannelPermission


async def get(s: AsyncSession, channel_id: int) -> Channel | None:
    return await s.get(Channel, channel_id)


async def upsert(s: AsyncSession, channel_id: int, **fields: Any) -> Channel:
    ch = await s.get(Channel, channel_id)
    if ch is None:
        ch = Channel(id=channel_id, **fields)
        s.add(ch)
    else:
        for k, v in fields.items():
            setattr(ch, k, v)
    await s.flush()
    return ch


async def list_by_status(s: AsyncSession, *statuses: str) -> list[Channel]:
    q = select(Channel).order_by(Channel.created_at.desc())
    if statuses:
        q = q.where(Channel.status.in_(statuses))
    res = await s.execute(q)
    return list(res.scalars())


async def list_all(s: AsyncSession) -> list[Channel]:
    res = await s.execute(select(Channel).order_by(Channel.created_at.desc()))
    return list(res.scalars())


async def list_for_user(s: AsyncSession, user_id: int) -> list[Channel]:
    q = (
        select(Channel)
        .join(ChannelPermission, ChannelPermission.channel_id == Channel.id)
        .where(ChannelPermission.user_id == user_id)
        .order_by(Channel.title)
    )
    res = await s.execute(q)
    return list(res.scalars().unique())


async def count_by_status(s: AsyncSession) -> dict[str, int]:
    res = await s.execute(select(Channel.status, func.count()).group_by(Channel.status))
    return {row[0]: row[1] for row in res.all()}
