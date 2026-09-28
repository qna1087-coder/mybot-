from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.models import ChannelPermission


async def grant(s: AsyncSession, channel_id: int, user_id: int, role: str, granted_by: int | None) -> ChannelPermission:
    res = await s.execute(
        select(ChannelPermission).where(
            ChannelPermission.channel_id == channel_id, ChannelPermission.user_id == user_id
        )
    )
    perm = res.scalar_one_or_none()
    if perm is None:
        perm = ChannelPermission(channel_id=channel_id, user_id=user_id, role=role, granted_by=granted_by)
        s.add(perm)
    else:
        perm.role = role
    await s.flush()
    return perm


async def revoke(s: AsyncSession, channel_id: int, user_id: int) -> None:
    await s.execute(
        delete(ChannelPermission).where(
            ChannelPermission.channel_id == channel_id, ChannelPermission.user_id == user_id
        )
    )


async def get_role(s: AsyncSession, channel_id: int, user_id: int) -> str | None:
    res = await s.execute(
        select(ChannelPermission.role).where(
            ChannelPermission.channel_id == channel_id, ChannelPermission.user_id == user_id
        )
    )
    return res.scalar_one_or_none()


async def list_for_channel(s: AsyncSession, channel_id: int) -> list[ChannelPermission]:
    res = await s.execute(
        select(ChannelPermission).where(ChannelPermission.channel_id == channel_id).order_by(ChannelPermission.role)
    )
    return list(res.scalars())
