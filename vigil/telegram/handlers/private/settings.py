"""Channel settings: language, time zone, managers, and system-level channel state."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core import glyphs as G
from vigil.core.timeutil import utcnow
from vigil.db.models import Channel, User
from vigil.db.repo import audit
from vigil.db.repo import permissions as perm_repo
from vigil.db.repo import users as user_repo
from vigil.services.context import Services
from vigil.telegram.callbacks import (
    A_CH_RESUME,
    A_CH_REVOKE,
    A_CH_SUSPEND,
    A_MANAGER_ADD,
    A_MANAGER_DEL,
    A_SET_LANG,
    A_SET_TZ,
    S_DASH,
    S_LANG,
    S_MANAGERS,
    S_SETTINGS,
    Act,
    Nav,
)
from vigil.telegram.handlers.private.common import (
    Input,
    cancel_kb,
    channel_state,
    guard_channel,
    resolve_user_ref,
)
from vigil.telegram.ui.screens import compose, kb, nav, show, toast
from vigil.telegram.ui.texts import SUPPORTED, esc, t

router = Router(name="private_settings")


async def settings_screen(ctx: Services, s: AsyncSession, ch: Channel, user: User, lang: str):
    is_system = await ctx.access.is_system_admin(s, user.id)
    owner = await user_repo.get(s, ch.owner_user_id) if ch.owner_user_id else None
    lines = [
        channel_state(lang, ch),
        f"{t(lang, 'id')} · <code>{ch.id}</code>",
        f"{t(lang, 'set_owner')} · {esc(owner.display) if owner else (ch.owner_user_id or t(lang, 'unknown'))}",
        f"{t(lang, 'set_timezone')} · {ch.timezone}",
        f"{t(lang, 'set_language')} · {t(lang, 'lang_' + lang)}",
    ]
    text = compose(f"{t(lang, 'set_title')} {G.DOT} {esc(ch.title)}", (None, lines))
    rows = [
        [(t(lang, "btn_language"), Nav(s=S_LANG, c=ch.id).pack()), (t(lang, "btn_timezone"), Act(a=A_SET_TZ, c=ch.id).pack())],
        [(t(lang, "btn_managers"), Nav(s=S_MANAGERS, c=ch.id).pack())],
    ]
    if is_system:
        if ch.status == "active":
            rows.append([(t(lang, "btn_ch_suspend"), Act(a=A_CH_SUSPEND, c=ch.id).pack()), (t(lang, "btn_ch_revoke"), Act(a=A_CH_REVOKE, c=ch.id).pack())])
        elif ch.status in ("suspended", "detached", "revoked"):
            rows.append([(t(lang, "btn_ch_resume"), Act(a=A_CH_RESUME, c=ch.id).pack()), (t(lang, "btn_ch_revoke"), Act(a=A_CH_REVOKE, c=ch.id).pack())])
    rows.append(nav(lang, back=Nav(s=S_DASH, c=ch.id).pack()))
    return text, kb(rows)


async def managers_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str):
    perms = await perm_repo.list_for_channel(s, ch.id)
    lines = []
    rows: list[list[tuple[str, str]]] = []
    for p in perms:
        u = await user_repo.get(s, p.user_id)
        name = u.display if u else str(p.user_id)
        lines.append(f"{G.SPARK if p.role == 'owner' else G.ACTIVE} {t(lang, 'mgr_row', name=esc(name), role=t(lang, 'role_' + p.role))}")
        if p.role != "owner":
            rows.append([(f"{t(lang, 'btn_remove')} · {esc(name)[:24]}", Act(a=A_MANAGER_DEL, c=ch.id, t=str(p.user_id)).pack())])
    text = compose(t(lang, "mgr_title"), t(lang, "mgr_hint"), (None, lines) if lines else None)
    rows.append([(t(lang, "btn_add_manager"), Act(a=A_MANAGER_ADD, c=ch.id).pack())])
    rows.append(nav(lang, back=Nav(s=S_SETTINGS, c=ch.id).pack()))
    return text, kb(rows)


@router.callback_query(Nav.filter(F.s == S_SETTINGS))
async def nav_settings(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    text, markup = await settings_screen(ctx, s, ch, user, lang)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Nav.filter(F.s == S_LANG))
async def nav_lang(cb: CallbackQuery, callback_data: Nav, lang: str) -> None:
    rows = [[(f"{G.ACTIVE if code == lang else G.OFF} {t(lang, 'lang_' + code)}", Act(a=A_SET_LANG, c=callback_data.c, t=code).pack()) for code in SUPPORTED]]
    rows.append(nav(lang, back=Nav(s=S_SETTINGS, c=callback_data.c).pack() if callback_data.c else Nav(s="home").pack()))
    await show(cb, compose(t(lang, "lang_title")), kb(rows))
    await cb.answer()


@router.callback_query(Act.filter(F.a == A_SET_LANG))
async def act_set_lang(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    code = callback_data.t if callback_data.t in SUPPORTED else "en"
    await user_repo.set_lang(s, user.id, code)
    user.lang = code
    if callback_data.c:
        ch = await guard_channel(cb, ctx, s, user, callback_data.c, code)
        if ch is None:
            return
        text, markup = await settings_screen(ctx, s, ch, user, code)
    else:
        from vigil.telegram.handlers.private.common import home

        text, markup = await home(ctx, s, user, code)
    await show(cb, text, markup)
    await toast(cb, t(code, "lang_saved"))


@router.callback_query(Act.filter(F.a == A_SET_TZ))
async def act_tz(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    await state.set_state(Input.tz)
    await state.update_data(c=ch.id)
    await cb.message.answer(t(lang, "tz_prompt"), reply_markup=cancel_kb(lang))
    await cb.answer()


@router.message(Input.tz, F.chat.type == "private")
async def input_tz(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(message, ctx, s, user, int(data.get("c", 0)), lang)
    if ch is None:
        await state.clear()
        return
    name = (message.text or "").strip()
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        await message.answer(t(lang, "tz_invalid"))
        return
    ch.timezone = name
    await s.flush()
    await audit.log(s, "setting.changed", channel_id=ch.id, actor=user.id, key="timezone", value=name)
    await state.clear()
    text, markup = await settings_screen(ctx, s, ch, user, lang)
    await message.answer(t(lang, "tz_saved", tz=name))
    await message.answer(text, reply_markup=markup)


@router.callback_query(Nav.filter(F.s == S_MANAGERS))
async def nav_managers(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    text, markup = await managers_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Act.filter(F.a == A_MANAGER_ADD))
async def act_manager_add(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    await state.set_state(Input.manager_user)
    await state.update_data(c=ch.id)
    await cb.message.answer(t(lang, "mgr_add_prompt"), reply_markup=cancel_kb(lang))
    await cb.answer()


@router.message(Input.manager_user, F.chat.type == "private")
async def input_manager(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(message, ctx, s, user, int(data.get("c", 0)), lang)
    if ch is None:
        await state.clear()
        return
    ref = resolve_user_ref(message)
    if ref is None or ref.is_bot:
        await message.answer(t(lang, "adda_invalid"))
        return
    await user_repo.ensure(s, ref.user_id, username=ref.username, first_name=ref.name or None)
    await perm_repo.grant(s, ch.id, ref.user_id, "manager", user.id)
    await audit.log(s, "manager.added", channel_id=ch.id, actor=user.id, target_type="user", target_id=ref.user_id)
    await state.clear()
    text, markup = await managers_screen(ctx, s, ch, lang)
    await message.answer(t(lang, "mgr_added"))
    await message.answer(text, reply_markup=markup)


@router.callback_query(Act.filter(F.a == A_MANAGER_DEL))
async def act_manager_del(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    uid = int(callback_data.t) if callback_data.t.lstrip("-").isdigit() else 0
    if uid == ch.owner_user_id:
        await toast(cb, t(lang, "mgr_cannot_remove_owner"), alert=True)
        return
    await perm_repo.revoke(s, ch.id, uid)
    await audit.log(s, "manager.removed", channel_id=ch.id, actor=user.id, target_type="user", target_id=uid)
    text, markup = await managers_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "mgr_removed"))


@router.callback_query(Act.filter(F.a.in_({A_CH_SUSPEND, A_CH_RESUME, A_CH_REVOKE})))
async def act_channel_state(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    from vigil.telegram.handlers.private.common import guard_system

    if not await guard_system(cb, ctx, s, user, lang):
        return
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    if callback_data.a == A_CH_REVOKE and callback_data.v != "ok":
        text = compose(t(lang, "ch_manage_title"), t(lang, "confirm_revoke", title=esc(ch.title)))
        markup = kb([[(t(lang, "confirm"), Act(a=A_CH_REVOKE, c=ch.id, v="ok").pack())], [(t(lang, "cancel"), Nav(s=S_SETTINGS, c=ch.id).pack())]])
        await show(cb, text, markup)
        await cb.answer()
        return
    mapping = {A_CH_SUSPEND: ("suspended", "channel.suspended", "ch_suspended_ok"), A_CH_RESUME: ("active", "channel.resumed", "ch_resumed_ok"), A_CH_REVOKE: ("revoked", "channel.revoked", "ch_revoked_ok")}
    status, action, msg = mapping[callback_data.a]
    await ctx.channels.set_status(s, ch.id, status, by=user.id, action=action)
    if status == "active":
        ch.authorized_at = ch.authorized_at or utcnow()
        await ctx.channels.sync_admins(s, ch)
    text, markup = await settings_screen(ctx, s, ch, user, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, msg))
