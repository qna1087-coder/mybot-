from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.models import AuditLog


async def log(
    s: AsyncSession,
    action: str,
    *,
    channel_id: int = 0,
    actor: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    **details: Any,
) -> AuditLog:
    row = AuditLog(
        channel_id=channel_id,
        actor_user_id=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details or None,
    )
    s.add(row)
    await s.flush()
    return row


async def list_entries(
    s: AsyncSession,
    *,
    channel_id: int | None = None,
    limit: int = 10,
    offset: int = 0,
    action_prefix: str | None = None,
) -> list[AuditLog]:
    q = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if channel_id is not None:
        q = q.where(AuditLog.channel_id == channel_id)
    if action_prefix:
        q = q.where(AuditLog.action.like(f"{action_prefix}%"))
    res = await s.execute(q.offset(offset).limit(limit))
    return list(res.scalars())


async def count(s: AsyncSession, channel_id: int | None = None, action_prefix: str | None = None) -> int:
    q = select(func.count()).select_from(AuditLog)
    if channel_id is not None:
        q = q.where(AuditLog.channel_id == channel_id)
    if action_prefix:
        q = q.where(AuditLog.action.like(f"{action_prefix}%"))
    res = await s.execute(q)
    return int(res.scalar_one())
