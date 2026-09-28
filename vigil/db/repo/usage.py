from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.models import ModerationUsage


async def get_day(s: AsyncSession, day: str) -> ModerationUsage | None:
    return await s.get(ModerationUsage, day)


async def bump(s: AsyncSession, day: str, *, model: str | None, ok: bool, error: str | None = None) -> ModerationUsage:
    row = await s.get(ModerationUsage, day)
    if row is None:
        row = ModerationUsage(day=day, requests=0, failures=0)
        s.add(row)
    row.requests += 1
    if not ok:
        row.failures += 1
        row.last_error = (error or "")[:255] or None
    if model:
        row.last_model = model
    await s.flush()
    return row
