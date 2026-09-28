from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.timeutil import utcnow
from vigil.db.models import Admin

LIVE_STATUSES = ("active", "suspended", "shielded", "unmanaged", "owner")


async def get(s: AsyncSession, admin_id: int) -> Admin | None:
    return await s.get(Admin, admin_id)


async def get_by_user(s: AsyncSession, channel_id: int, user_id: int) -> Admin | None:
    res = await s.execute(select(Admin).where(Admin.channel_id == channel_id, Admin.user_id == user_id))
    return res.scalar_one_or_none()


async def list_for_channel(s: AsyncSession, channel_id: int, statuses: Iterable[str] | None = None) -> list[Admin]:
    q = select(Admin).where(Admin.channel_id == channel_id)
    q = q.where(Admin.status.in_(tuple(statuses) if statuses else LIVE_STATUSES))
    q = q.order_by(Admin.status, Admin.full_name)
    res = await s.execute(q)
    return list(res.scalars())


async def upsert(s: AsyncSession, channel_id: int, user_id: int, **fields: Any) -> Admin:
    admin = await get_by_user(s, channel_id, user_id)
    if admin is None:
        admin = Admin(channel_id=channel_id, user_id=user_id, **fields)
        s.add(admin)
    else:
        for k, v in fields.items():
            setattr(admin, k, v)
        admin.updated_at = utcnow()
    await s.flush()
    return admin


async def mark_removed_except(s: AsyncSession, channel_id: int, keep_user_ids: set[int]) -> list[Admin]:
    """Admins no longer in Telegram's list. Suspended/shielded admins are kept (they are ours)."""
    res = await s.execute(
        select(Admin).where(
            Admin.channel_id == channel_id,
            Admin.status.in_(("active", "unmanaged", "owner")),
        )
    )
    removed: list[Admin] = []
    for a in res.scalars():
        if a.user_id not in keep_user_ids:
            a.status = "removed"
            a.updated_at = utcnow()
            removed.append(a)
    await s.flush()
    return removed


async def count_by_status(s: AsyncSession, channel_id: int) -> dict[str, int]:
    res = await s.execute(
        select(Admin.status, func.count()).where(Admin.channel_id == channel_id).group_by(Admin.status)
    )
    return {row[0]: row[1] for row in res.all()}


async def list_shieldable(s: AsyncSession, channel_id: int) -> list[Admin]:
    res = await s.execute(
        select(Admin).where(
            Admin.channel_id == channel_id,
            Admin.status == "active",
            Admin.managed_by_bot.is_(True),
            Admin.shield_exempt.is_(False),
        )
    )
    return list(res.scalars())
