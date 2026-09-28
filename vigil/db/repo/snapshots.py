from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.timeutil import utcnow
from vigil.db.models import AdminSnapshot


async def create(
    s: AsyncSession,
    *,
    channel_id: int,
    user_id: int,
    admin_id: int | None,
    rights: dict[str, Any],
    custom_title: str | None,
    reason: str,
) -> AdminSnapshot:
    snap = AdminSnapshot(
        channel_id=channel_id,
        user_id=user_id,
        admin_id=admin_id,
        rights=rights,
        custom_title=custom_title,
        reason=reason,
    )
    s.add(snap)
    await s.flush()
    return snap


async def get(s: AsyncSession, snapshot_id: int) -> AdminSnapshot | None:
    return await s.get(AdminSnapshot, snapshot_id)


async def latest_unrestored(s: AsyncSession, channel_id: int, user_id: int) -> AdminSnapshot | None:
    res = await s.execute(
        select(AdminSnapshot)
        .where(
            AdminSnapshot.channel_id == channel_id,
            AdminSnapshot.user_id == user_id,
            AdminSnapshot.restored_at.is_(None),
        )
        .order_by(AdminSnapshot.taken_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def latest_any(s: AsyncSession, channel_id: int, user_id: int) -> AdminSnapshot | None:
    res = await s.execute(
        select(AdminSnapshot)
        .where(AdminSnapshot.channel_id == channel_id, AdminSnapshot.user_id == user_id)
        .order_by(AdminSnapshot.taken_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def mark_restored(s: AsyncSession, snap: AdminSnapshot, by: int | None) -> None:
    snap.restored_at = utcnow()
    snap.restored_by = by
    snap.restore_error = None
    await s.flush()


async def mark_failed(s: AsyncSession, snap: AdminSnapshot, error: str) -> None:
    snap.restore_error = error[:255]
    await s.flush()
