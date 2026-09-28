from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.timeutil import utcnow
from vigil.db.models import EmojiAllow, EmojiPack


async def allowed_ids(s: AsyncSession, channel_id: int) -> set[str]:
    res = await s.execute(
        select(EmojiAllow.custom_emoji_id).where(EmojiAllow.channel_id.in_((0, channel_id)))
    )
    return {row[0] for row in res.all()}


async def list_allow(s: AsyncSession, channel_id: int, *, limit: int = 30, offset: int = 0) -> list[EmojiAllow]:
    res = await s.execute(
        select(EmojiAllow)
        .where(EmojiAllow.channel_id == channel_id)
        .order_by(EmojiAllow.set_name, EmojiAllow.added_at)
        .offset(offset)
        .limit(limit)
    )
    return list(res.scalars())


async def count_allow(s: AsyncSession, channel_id: int) -> int:
    res = await s.execute(select(func.count()).select_from(EmojiAllow).where(EmojiAllow.channel_id == channel_id))
    return int(res.scalar_one())


async def get_allow(s: AsyncSession, channel_id: int, custom_emoji_id: str) -> EmojiAllow | None:
    res = await s.execute(
        select(EmojiAllow).where(EmojiAllow.channel_id == channel_id, EmojiAllow.custom_emoji_id == custom_emoji_id)
    )
    return res.scalar_one_or_none()


async def add_ids(s: AsyncSession, channel_id: int, items: list[dict[str, Any]], *, source: str, by: int | None) -> int:
    """items: [{custom_emoji_id, set_name, emoji}] → number newly added."""
    existing = await allowed_ids_for_channel(s, channel_id)
    added = 0
    for it in items:
        cid = str(it["custom_emoji_id"])
        if cid in existing:
            continue
        s.add(
            EmojiAllow(
                channel_id=channel_id,
                custom_emoji_id=cid,
                set_name=it.get("set_name"),
                emoji=it.get("emoji"),
                source=source,
                added_by=by,
            )
        )
        existing.add(cid)
        added += 1
    await s.flush()
    return added


async def allowed_ids_for_channel(s: AsyncSession, channel_id: int) -> set[str]:
    res = await s.execute(select(EmojiAllow.custom_emoji_id).where(EmojiAllow.channel_id == channel_id))
    return {row[0] for row in res.all()}


async def remove_id(s: AsyncSession, channel_id: int, custom_emoji_id: str) -> int:
    res = await s.execute(
        delete(EmojiAllow).where(EmojiAllow.channel_id == channel_id, EmojiAllow.custom_emoji_id == custom_emoji_id)
    )
    return res.rowcount or 0


async def list_packs(s: AsyncSession, channel_id: int) -> list[EmojiPack]:
    res = await s.execute(select(EmojiPack).where(EmojiPack.channel_id == channel_id).order_by(EmojiPack.title))
    return list(res.scalars())


async def get_pack(s: AsyncSession, channel_id: int, set_name: str) -> EmojiPack | None:
    res = await s.execute(select(EmojiPack).where(EmojiPack.channel_id == channel_id, EmojiPack.set_name == set_name))
    return res.scalar_one_or_none()


async def upsert_pack(s: AsyncSession, channel_id: int, set_name: str, title: str, count: int, by: int | None) -> EmojiPack:
    pack = await get_pack(s, channel_id, set_name)
    if pack is None:
        pack = EmojiPack(channel_id=channel_id, set_name=set_name, title=title, emoji_count=count, added_by=by)
        s.add(pack)
    else:
        pack.title = title
        pack.emoji_count = count
        pack.synced_at = utcnow()
    await s.flush()
    return pack


async def remove_pack(s: AsyncSession, channel_id: int, set_name: str) -> int:
    res = await s.execute(
        delete(EmojiAllow).where(
            EmojiAllow.channel_id == channel_id, EmojiAllow.set_name == set_name, EmojiAllow.source == "pack"
        )
    )
    await s.execute(delete(EmojiPack).where(EmojiPack.channel_id == channel_id, EmojiPack.set_name == set_name))
    return res.rowcount or 0
