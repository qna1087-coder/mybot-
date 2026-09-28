from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.timeutil import utcnow
from vigil.db.models import User


async def get(s: AsyncSession, user_id: int) -> User | None:
    return await s.get(User, user_id)


async def upsert_from_tg(s: AsyncSession, tg_user: Any, *, default_lang: str = "en") -> User:
    user = await s.get(User, tg_user.id)
    if user is None:
        lang = default_lang
        code = (getattr(tg_user, "language_code", None) or "").lower()
        if code.startswith("ar"):
            lang = "ar"
        user = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            lang=lang,
        )
        s.add(user)
    else:
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        user.last_seen_at = utcnow()
    await s.flush()
    return user


async def ensure(s: AsyncSession, user_id: int, **fields: Any) -> User:
    user = await s.get(User, user_id)
    if user is None:
        user = User(id=user_id, **fields)
        s.add(user)
        await s.flush()
    return user


async def set_role(s: AsyncSession, user_id: int, role: str) -> User:
    user = await ensure(s, user_id)
    user.role = role
    await s.flush()
    return user


async def list_by_role(s: AsyncSession, role: str) -> list[User]:
    res = await s.execute(select(User).where(User.role == role).order_by(User.created_at))
    return list(res.scalars())


async def set_lang(s: AsyncSession, user_id: int, lang: str) -> None:
    user = await ensure(s, user_id)
    user.lang = lang
    await s.flush()


async def set_dm_ok(s: AsyncSession, user_id: int, ok: bool) -> None:
    user = await s.get(User, user_id)
    if user is not None:
        user.dm_ok = ok
        await s.flush()
