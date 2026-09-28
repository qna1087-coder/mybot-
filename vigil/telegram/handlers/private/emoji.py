"""Premium emoji allowlist: packs (via getStickerSet) and single IDs (via getCustomEmojiStickers)."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core import glyphs as G
from vigil.core.retry import short_error, tg
from vigil.db.models import Channel, User
from vigil.db.repo import audit
from vigil.db.repo import emoji as repo
from vigil.services.context import Services
from vigil.services.guard.emoji import extract_custom_emoji
from vigil.telegram.callbacks import (
    A_EMOJI_ADD_ONE,
    A_EMOJI_ADD_PACK,
    A_EMOJI_CHECK,
    A_EMOJI_REMOVE_ID,
    A_EMOJI_REMOVE_PACK,
    A_EMOJI_SYNC_PACK,
    S_DASH,
    S_EMOJI,
    S_EMOJI_IDS,
    Act,
    Nav,
)
from vigil.telegram.handlers.private.common import Input, cancel_kb, guard_channel
from vigil.telegram.ui.screens import compose, kb, nav, pager, paginate, show, toast
from vigil.telegram.ui.texts import esc, t

router = Router(name="private_emoji")

_SET_RE = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/(?:addemoji|addstickers)/([A-Za-z0-9_]+)", re.IGNORECASE)
_ID_RE = re.compile(r"\d{15,25}")


def parse_set_name(text: str) -> str | None:
    text = text.strip()
    m = _SET_RE.search(text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_]{3,64}", text):
        return text
    return None


async def emoji_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str, page: int = 0):
    packs = await repo.list_packs(s, ch.id)
    singles = await repo.count_allow(s, ch.id)
    pack_ids = sum(p.emoji_count for p in packs)
    singles_only = max(singles - pack_ids, 0)
    items, page, total = paginate(packs, page, 6)
    if not packs and not singles:
        body = [t(lang, "emo_empty")]
    else:
        body = [t(lang, "emo_summary", packs=len(packs), singles=singles_only)]
    text = compose(f"{t(lang, 'emo_title')} {G.DOT} {esc(ch.title)}", (None, body), footer=t(lang, "emo_hint") if packs or singles else None)
    rows: list[list[tuple[str, str]]] = []
    for p in items:
        rows.append([
            (f"{G.ACTIVE} {esc(p.title or p.set_name)[:24]} · {p.emoji_count}", Act(a=A_EMOJI_SYNC_PACK, c=ch.id, t=str(p.id)).pack()),
            (t(lang, "btn_remove_pack"), Act(a=A_EMOJI_REMOVE_PACK, c=ch.id, t=str(p.id)).pack()),
        ])
    rows.append(pager(lang, screen=S_EMOJI, channel=ch.id, arg="", page=page, total_pages=total))
    rows.append([(t(lang, "btn_add_pack"), Act(a=A_EMOJI_ADD_PACK, c=ch.id).pack()), (t(lang, "btn_add_emoji"), Act(a=A_EMOJI_ADD_ONE, c=ch.id).pack())])
    rows.append([(t(lang, "btn_check"), Act(a=A_EMOJI_CHECK, c=ch.id).pack()), (t(lang, "btn_list_ids"), Nav(s=S_EMOJI_IDS, c=ch.id).pack())])
    rows.append(nav(lang, back=Nav(s=S_DASH, c=ch.id).pack()))
    return text, kb(rows)


async def ids_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str, page: int = 0):
    all_rows = [e for e in await repo.list_allow(s, ch.id, limit=500) if e.source == "manual"]
    items, page, total = paginate(all_rows, page, 8)
    text = compose(t(lang, "emo_ids_title"), t(lang, "emo_ids_empty") if not all_rows else f"{len(all_rows)}")
    rows = [[(f"{e.emoji or '·'} {e.custom_emoji_id}", Act(a=A_EMOJI_REMOVE_ID, c=ch.id, t=e.custom_emoji_id).pack())] for e in items]
    rows.append(pager(lang, screen=S_EMOJI_IDS, channel=ch.id, arg="", page=page, total_pages=total))
    rows.append(nav(lang, back=Nav(s=S_EMOJI, c=ch.id).pack()))
    return text, kb(rows)


async def _fetch_pack(ctx: Services, name: str):
    try:
        return await tg(lambda: ctx.bot.get_sticker_set(name), label="getStickerSet"), None
    except TelegramAPIError as e:
        return None, short_error(e)


async def _add_pack(ctx: Services, s: AsyncSession, ch: Channel, name: str, by: int, lang: str) -> str:
    sticker_set, err = await _fetch_pack(ctx, name)
    if sticker_set is None:
        return t(lang, "emo_pack_not_found") if err and ("invalid" in err.lower() or "not found" in err.lower()) else t(lang, "err_telegram", error=esc(err or ""))
    if sticker_set.sticker_type != "custom_emoji":
        return t(lang, "emo_pack_not_emoji")
    items = [{"custom_emoji_id": st.custom_emoji_id, "set_name": sticker_set.name, "emoji": st.emoji} for st in sticker_set.stickers if st.custom_emoji_id]
    existed = await repo.get_pack(s, ch.id, sticker_set.name)
    await repo.add_ids(s, ch.id, items, source="pack", by=by)
    await repo.upsert_pack(s, ch.id, sticker_set.name, sticker_set.title, len(items), by)
    await audit.log(s, "emoji.pack_added", channel_id=ch.id, actor=by, target_type="pack", target_id=sticker_set.name, count=len(items))
    key = "emo_pack_synced" if existed else "emo_pack_added"
    return t(lang, key, title=esc(sticker_set.title), n=len(items))


@router.callback_query(Nav.filter(F.s == S_EMOJI))
async def nav_emoji(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    text, markup = await emoji_screen(ctx, s, ch, lang, callback_data.p)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Nav.filter(F.s == S_EMOJI_IDS))
async def nav_ids(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    text, markup = await ids_screen(ctx, s, ch, lang, callback_data.p)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Act.filter(F.a.in_({A_EMOJI_ADD_PACK, A_EMOJI_ADD_ONE, A_EMOJI_CHECK})))
async def act_prompt(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    mapping = {A_EMOJI_ADD_PACK: (Input.emoji_pack, "emo_add_pack_prompt"), A_EMOJI_ADD_ONE: (Input.emoji_one, "emo_add_emoji_prompt"), A_EMOJI_CHECK: (Input.emoji_check, "emo_check_prompt")}
    st, key = mapping[callback_data.a]
    await state.set_state(st)
    await state.update_data(c=ch.id)
    await cb.message.answer(t(lang, key), reply_markup=cancel_kb(lang))
    await cb.answer()


@router.message(Input.emoji_pack, F.chat.type == "private")
async def input_pack(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(message, ctx, s, user, int(data.get("c", 0)), lang)
    if ch is None:
        await state.clear()
        return
    name = parse_set_name(message.text or "")
    if not name:
        await message.answer(t(lang, "emo_pack_not_found"))
        return
    result = await _add_pack(ctx, s, ch, name, user.id, lang)
    await state.clear()
    text, markup = await emoji_screen(ctx, s, ch, lang)
    await message.answer(result)
    await message.answer(text, reply_markup=markup)


async def _ids_from_message(ctx: Services, message: Message) -> list[dict]:
    found = extract_custom_emoji(message)
    ids = [cid for cid, _ in found] or _ID_RE.findall(message.text or "")
    if not ids:
        return []
    stickers = []
    try:
        stickers = await tg(lambda: ctx.bot.get_custom_emoji_stickers(custom_emoji_ids=list(dict.fromkeys(ids))[:200]), label="getCustomEmojiStickers")
    except TelegramAPIError:
        pass
    by_id = {st.custom_emoji_id: st for st in stickers if st.custom_emoji_id}
    visible = dict(found)
    out = []
    for cid in dict.fromkeys(ids):
        st = by_id.get(cid)
        out.append({"custom_emoji_id": cid, "set_name": st.set_name if st else None, "emoji": (st.emoji if st else None) or visible.get(cid), "known": st is not None})
    return out


@router.message(Input.emoji_one, F.chat.type == "private")
async def input_one(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(message, ctx, s, user, int(data.get("c", 0)), lang)
    if ch is None:
        await state.clear()
        return
    items = await _ids_from_message(ctx, message)
    if not items:
        await message.answer(t(lang, "emo_none_found"))
        return
    added = await repo.add_ids(s, ch.id, items, source="manual", by=user.id)
    await audit.log(s, "emoji.added", channel_id=ch.id, actor=user.id, ids=[i["custom_emoji_id"] for i in items][:20])
    await state.clear()
    text, markup = await emoji_screen(ctx, s, ch, lang)
    await message.answer(t(lang, "emo_added", n=added))
    await message.answer(text, reply_markup=markup)


@router.message(Input.emoji_check, F.chat.type == "private")
async def input_check(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(message, ctx, s, user, int(data.get("c", 0)), lang)
    if ch is None:
        await state.clear()
        return
    items = await _ids_from_message(ctx, message)
    if not items:
        await message.answer(t(lang, "emo_none_found"))
        return
    allowed = await repo.allowed_ids(s, ch.id)
    lines = []
    for it in items[:10]:
        if not it["known"] and not it["emoji"]:
            lines.append(f"{t(lang, 'emo_check_unknown')} · <code>{it['custom_emoji_id']}</code>")
            continue
        key = "emo_check_allowed" if it["custom_emoji_id"] in allowed else "emo_check_blocked"
        lines.append(t(lang, key, emoji=it["emoji"] or "·", id=it["custom_emoji_id"], set=esc(it["set_name"] or "?")))
    await state.clear()
    await message.answer("\n\n".join(lines), reply_markup=kb([nav(lang, back=Nav(s=S_EMOJI, c=ch.id).pack())]))


@router.callback_query(Act.filter(F.a.in_({A_EMOJI_SYNC_PACK, A_EMOJI_REMOVE_PACK})))
async def act_pack(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    packs = {str(p.id): p for p in await repo.list_packs(s, ch.id)}
    pack = packs.get(callback_data.t)
    if pack is None:
        await toast(cb, t(lang, "toast_nothing"))
        return
    if callback_data.a == A_EMOJI_SYNC_PACK:
        msg = await _add_pack(ctx, s, ch, pack.set_name, user.id, lang)
    else:
        n = await repo.remove_pack(s, ch.id, pack.set_name)
        await audit.log(s, "emoji.pack_removed", channel_id=ch.id, actor=user.id, target_type="pack", target_id=pack.set_name, count=n)
        msg = t(lang, "emo_pack_removed", n=n)
    text, markup = await emoji_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, re.sub(r"<[^>]+>", "", msg), alert=True)


@router.callback_query(Act.filter(F.a == A_EMOJI_REMOVE_ID))
async def act_remove_id(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    n = await repo.remove_id(s, ch.id, callback_data.t)
    if n:
        await audit.log(s, "emoji.removed", channel_id=ch.id, actor=user.id, target_type="emoji", target_id=callback_data.t)
    text, markup = await ids_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "emo_removed") if n else t(lang, "toast_nothing"))
