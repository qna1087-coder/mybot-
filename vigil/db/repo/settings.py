from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.models import Setting


async def get_all(s: AsyncSession, channel_id: int) -> dict[str, Any]:
    res = await s.execute(select(Setting).where(Setting.channel_id == channel_id))
    return {row.key: (row.value or {}).get("v") for row in res.scalars()}


async def set_value(s: AsyncSession, channel_id: int, key: str, value: Any, by: int | None) -> None:
    res = await s.execute(select(Setting).where(Setting.channel_id == channel_id, Setting.key == key))
    row = res.scalar_one_or_none()
    if row is None:
        s.add(Setting(channel_id=channel_id, key=key, value={"v": value}, updated_by=by))
    else:
        row.value = {"v": value}
        row.updated_by = by
    await s.flush()


async def unset(s: AsyncSession, channel_id: int, key: str) -> None:
    await s.execute(delete(Setting).where(Setting.channel_id == channel_id, Setting.key == key))
