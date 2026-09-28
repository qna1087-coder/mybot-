"""Content Guard settings: toggles, cycles, media policy, categories, letter limit."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core import glyphs as G
from vigil.db.models import Channel, User
from vigil.db.repo import audit
from vigil.services.context import Services
from vigil.services.settings import MEDIA_POLICY_VALUES, MEDIA_TYPES, MODERATION_CATEGORIES
from vigil.telegram.callbacks import (
    A_CATEGORY,
    A_CYCLE,
    A_LIMIT_SET,
    A_MEDIA_COUNT,
    A_MEDIA_POLICY,
    A_TOGGLE,
    S_CATEGORIES,
    S_DASH,
    S_GUARD,
    S_MEDIA,
    Act,
    Nav,
)
from vigil.telegram.handlers.private.common import Input, cancel_kb, guard_channel
from vigil.telegram.ui.screens import compose, kb, nav, show, toast
from vigil.telegram.ui.texts import t

router = Router(name="private_guard")

TOGGLES = ("guard_enabled", "links_guard", "mentions_guard", "forwards_guard", "media_guard", "emoji_guard",
           "language_guard", "english_moderation", "foreign_latin_violation", "delete_offending_message",
           "notify_system_owner", "unattributed_alerts")
LABEL = {
    "guard_enabled": "grd_master", "links_guard": "grd_links", "mentions_guard": "grd_mentions",
    "forwards_guard": "grd_forwards", "media_guard": "grd_media", "emoji_guard": "grd_emoji",
    "language_guard": "grd_language", "english_moderation": "grd_english_api",
    "foreign_latin_violation": "grd_foreign_latin", "delete_offending_message": "grd_delete_msg",
    "notify_system_owner": "grd_notify_system", "unattributed_alerts": "grd_unattributed",
}
CYCLES = {
    "length_action": (("delete", "act_delete"), ("demote", "act_demote")),
    "violation_action": (("demote", "act_demote"), ("delete_only", "act_delete_only"), ("notify_only", "act_notify_only")),
    "api_fail_mode": (("default", "fail_default"), ("open", "fail_open"), ("closed", "fail_closed")),
}


def _cycle_label(lang: str, key: str, value: str) -> str:
    for v, label in CYCLES[key]:
        if v == value:
            return t(lang, label)
    return value


async def guard_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str):
    st = await ctx.settings.get(s, ch.id)

    def g(key: str) -> str:
        return G.ACTIVE if st.get(key) else G.OFF

    lines = [
        f"{g('guard_enabled')} {t(lang, 'grd_master')}",
        "",
        f"{g('links_guard')} {t(lang, 'grd_links')}   {g('mentions_guard')} {t(lang, 'grd_mentions')}   {g('forwards_guard')} {t(lang, 'grd_forwards')}",
        f"{g('media_guard')} {t(lang, 'grd_media')}   {g('emoji_guard')} {t(lang, 'grd_emoji')}",
        f"{g('language_guard')} {t(lang, 'grd_language')}   {g('english_moderation')} {t(lang, 'grd_english_api')}",
        f"{g('foreign_latin_violation')} {t(lang, 'grd_foreign_latin')}",
        "",
        f"{t(lang, 'grd_char_limit')} · <b>{st.english_char_limit}</b> → {_cycle_label(lang, 'length_action', st.length_action)}",
        f"{t(lang, 'grd_violation_action')} · <b>{_cycle_label(lang, 'violation_action', st.violation_action)}</b>",
        f"{g('delete_offending_message')} {t(lang, 'grd_delete_msg')}",
        f"{t(lang, 'grd_api_fail')} · <b>{_cycle_label(lang, 'api_fail_mode', st.api_fail_mode)}</b>",
        f"{g('notify_system_owner')} {t(lang, 'grd_notify_system')}   {g('unattributed_alerts')} {t(lang, 'grd_unattributed')}",
    ]
    text = compose(f"{t(lang, 'grd_title')} {G.DOT} {ch.title}", (None, lines), footer=t(lang, "grd_footer"))

    def tg(key: str) -> tuple[str, str]:
        return (f"{g(key)} {t(lang, LABEL[key])}", Act(a=A_TOGGLE, c=ch.id, t=key).pack())

    def cy(key: str, label_key: str) -> tuple[str, str]:
        return (f"{t(lang, label_key)} · {_cycle_label(lang, key, st.get(key))}", Act(a=A_CYCLE, c=ch.id, t=key).pack())

    rows = [
        [tg("guard_enabled")],
        [tg("links_guard"), tg("mentions_guard")],
        [tg("forwards_guard"), tg("media_guard")],
        [tg("emoji_guard"), tg("language_guard")],
        [tg("english_moderation"), tg("foreign_latin_violation")],
        [(f"{t(lang, 'btn_set_limit')} · {st.english_char_limit}", Act(a=A_LIMIT_SET, c=ch.id).pack()), cy("length_action", "grd_length_action")],
        [cy("violation_action", "grd_violation_action"), tg("delete_offending_message")],
        [cy("api_fail_mode", "grd_api_fail"), tg("notify_system_owner")],
        [(t(lang, "btn_media_policy"), Nav(s=S_MEDIA, c=ch.id).pack()), (t(lang, "btn_categories"), Nav(s=S_CATEGORIES, c=ch.id).pack())],
        nav(lang, back=Nav(s=S_DASH, c=ch.id).pack()),
    ]
    return text, kb(rows)


async def media_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str):
    st = await ctx.settings.get(s, ch.id)
    pol_glyph = {"allow": G.ACTIVE, "limited": G.WAITING, "block": G.OFF}
    lines = [f"{pol_glyph[st.media_policy_for(m)]} {t(lang, 'mt_' + m)} · {t(lang, 'pol_' + st.media_policy_for(m))}" for m in MEDIA_TYPES]
    text = compose(t(lang, "med_title"), (None, lines), (t(lang, "med_count"), [f"<b>{st.allowed_image_count}</b>"]), footer=t(lang, "med_hint"))
    rows = [[(f"{pol_glyph[st.media_policy_for(m)]} {t(lang, 'mt_' + m)} · {t(lang, 'pol_' + st.media_policy_for(m))}", Act(a=A_MEDIA_POLICY, c=ch.id, t=m).pack())] for m in MEDIA_TYPES]
    rows.append([("−", Act(a=A_MEDIA_COUNT, c=ch.id, v="-").pack()), (f"{t(lang, 'med_count')} · {st.allowed_image_count}", Act(a=A_MEDIA_COUNT, c=ch.id, v="0").pack()), ("+", Act(a=A_MEDIA_COUNT, c=ch.id, v="+").pack())])
    rows.append(nav(lang, back=Nav(s=S_GUARD, c=ch.id).pack()))
    return text, kb(rows)


async def categories_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str):
    st = await ctx.settings.get(s, ch.id)
    enabled = set(st.moderation_categories or [])
    text = compose(t(lang, "cat_title"), t(lang, "cat_hint"))
    cats = list(MODERATION_CATEGORIES)
    rows = [[(f"{G.ACTIVE if c in enabled else G.OFF} {t(lang, 'cat_' + c)}", Act(a=A_CATEGORY, c=ch.id, t=c).pack()) for c in cats[i:i + 2]] for i in range(0, len(cats), 2)]
    rows.append(nav(lang, back=Nav(s=S_GUARD, c=ch.id).pack()))
    return text, kb(rows)


@router.callback_query(Nav.filter(F.s.in_({S_GUARD, S_MEDIA, S_CATEGORIES})))
async def nav_guard(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    fn = {S_GUARD: guard_screen, S_MEDIA: media_screen, S_CATEGORIES: categories_screen}[callback_data.s]
    text, markup = await fn(ctx, s, ch, lang)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Act.filter(F.a == A_TOGGLE))
async def act_toggle(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None or callback_data.t not in TOGGLES:
        return
    value = await ctx.settings.toggle(s, ch.id, callback_data.t, user.id)
    await audit.log(s, "setting.changed", channel_id=ch.id, actor=user.id, key=callback_data.t, value=value)
    text, markup = await guard_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "toast_saved"))


@router.callback_query(Act.filter(F.a == A_CYCLE))
async def act_cycle(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None or callback_data.t not in CYCLES:
        return
    st = await ctx.settings.get(s, ch.id)
    values = [v for v, _ in CYCLES[callback_data.t]]
    current = st.get(callback_data.t)
    nxt = values[(values.index(current) + 1) % len(values)] if current in values else values[0]
    await ctx.settings.set(s, ch.id, callback_data.t, nxt, user.id)
    await audit.log(s, "setting.changed", channel_id=ch.id, actor=user.id, key=callback_data.t, value=nxt)
    text, markup = await guard_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "toast_saved"))


@router.callback_query(Act.filter(F.a == A_MEDIA_POLICY))
async def act_media_policy(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None or callback_data.t not in MEDIA_TYPES:
        return
    st = await ctx.settings.get(s, ch.id)
    current = st.media_policy_for(callback_data.t)
    nxt = MEDIA_POLICY_VALUES[(MEDIA_POLICY_VALUES.index(current) + 1) % len(MEDIA_POLICY_VALUES)]
    await ctx.settings.set_media_policy(s, ch.id, callback_data.t, nxt, user.id)
    await audit.log(s, "setting.changed", channel_id=ch.id, actor=user.id, key=f"media_policy.{callback_data.t}", value=nxt)
    text, markup = await media_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "toast_saved"))


@router.callback_query(Act.filter(F.a == A_MEDIA_COUNT))
async def act_media_count(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    if callback_data.v == "0":
        await cb.answer()
        return
    st = await ctx.settings.get(s, ch.id)
    n = max(0, min(10, int(st.allowed_image_count or 0) + (1 if callback_data.v == "+" else -1)))
    await ctx.settings.set(s, ch.id, "allowed_image_count", n, user.id)
    await audit.log(s, "setting.changed", channel_id=ch.id, actor=user.id, key="allowed_image_count", value=n)
    text, markup = await media_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "toast_saved"))


@router.callback_query(Act.filter(F.a == A_CATEGORY))
async def act_category(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None or callback_data.t not in MODERATION_CATEGORIES:
        return
    st = await ctx.settings.get(s, ch.id)
    enabled = set(st.moderation_categories or [])
    enabled ^= {callback_data.t}
    ordered = [c for c in MODERATION_CATEGORIES if c in enabled]
    await ctx.settings.set(s, ch.id, "moderation_categories", ordered, user.id)
    await audit.log(s, "setting.changed", channel_id=ch.id, actor=user.id, key="moderation_categories", value=ordered)
    text, markup = await categories_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "toast_saved"))


@router.callback_query(Act.filter(F.a == A_LIMIT_SET))
async def act_limit(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    st = await ctx.settings.get(s, ch.id)
    await state.set_state(Input.limit)
    await state.update_data(c=ch.id)
    await cb.message.answer(t(lang, "limit_prompt", n=st.english_char_limit), reply_markup=cancel_kb(lang))
    await cb.answer()


@router.message(Input.limit, F.chat.type == "private")
async def input_limit(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(message, ctx, s, user, int(data.get("c", 0)), lang)
    if ch is None:
        await state.clear()
        return
    raw = (message.text or "").strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if not raw.isdigit() or int(raw) > 4096:
        await message.answer(t(lang, "limit_invalid"))
        return
    n = int(raw)
    await ctx.settings.set(s, ch.id, "english_char_limit", n, user.id)
    await audit.log(s, "setting.changed", channel_id=ch.id, actor=user.id, key="english_char_limit", value=n)
    await state.clear()
    text, markup = await guard_screen(ctx, s, ch, lang)
    await message.answer(t(lang, "limit_saved", n=n))
    await message.answer(text, reply_markup=markup)
