"""System panel: pending activations, all channels, system admins, health."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core import glyphs as G
from vigil.core.timeutil import humanize_duration, utcnow
from vigil.db.models import User
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import audit
from vigil.db.repo import channels as ch_repo
from vigil.db.repo import shield as shield_repo
from vigil.db.repo import users as user_repo
from vigil.services.context import Services
from vigil.telegram.callbacks import (
    A_ACTIVATE,
    A_DECLINE,
    A_SYSADMIN_ADD,
    A_SYSADMIN_DEL,
    S_ALL_CHANNELS,
    S_DASH,
    S_HEALTH,
    S_PENDING,
    S_SYS_ADMINS,
    S_SYSTEM,
    Act,
    Nav,
)
from vigil.telegram.handlers.private.common import (
    Input,
    cancel_kb,
    channel_state,
    guard_system,
    resolve_user_ref,
)
from vigil.telegram.ui.screens import compose, kb, nav, pager, paginate, show, toast
from vigil.telegram.ui.texts import esc, t

router = Router(name="private_system")


async def system_screen(ctx: Services, s: AsyncSession, lang: str):
    counts = await ch_repo.count_by_status(s)
    active = counts.get("active", 0)
    pending = counts.get("pending", 0)
    other = sum(v for k, v in counts.items() if k not in ("active", "pending"))
    mod = ctx.moderation.status()
    if mod["enabled"]:
        mod_line = f"{G.ACTIVE if not mod['budget_exhausted'] else G.ATTENTION} " + t(lang, "sys_moderation_line", used=mod["requests_today"], budget=mod["budget"], model=esc((mod["last_model"] or mod["chain"][0]).split('/')[-1]))
    else:
        mod_line = f"{G.OFF} {t(lang, 'sys_moderation_off')}"
    sessions = await shield_repo.list_active_sessions(s)
    uptime = humanize_duration(int((utcnow() - ctx.started_at).total_seconds()), lang)
    text = compose(
        f"{G.SPARK} {t(lang, 'sys_title')}",
        (t(lang, "sys_channels"), [f"{G.ACTIVE} {t(lang, 'sys_channels_line', active=active, pending=pending, other=other)}"]),
        (t(lang, "sys_moderation"), [mod_line]),
        (t(lang, "sys_shield"), [f"{G.SHIELDED if sessions else G.OFF} {len(sessions)}"]),
        (t(lang, "sys_uptime"), [uptime]),
    )
    rows = [
        [(t(lang, "btn_pending", n=pending), Nav(s=S_PENDING).pack()), (t(lang, "btn_all_channels"), Nav(s=S_ALL_CHANNELS).pack())],
        [(t(lang, "btn_sys_admins"), Nav(s=S_SYS_ADMINS).pack()), (t(lang, "btn_health"), Nav(s=S_HEALTH).pack())],
        nav(lang, home=True, refresh=Nav(s=S_SYSTEM).pack()),
    ]
    return text, kb(rows)


async def pending_screen(ctx: Services, s: AsyncSession, lang: str, page: int):
    pend = await ch_repo.list_by_status(s, "pending")
    items, page, total = paginate(pend, page, 4)
    blocks = []
    rows: list[list[tuple[str, str]]] = []
    for ch in items:
        adder = await user_repo.get(s, ch.added_by) if ch.added_by else None
        owner = await admin_repo.get_by_user(s, ch.id, ch.owner_user_id) if ch.owner_user_id else None
        blocks.append(t(lang, "pend_card", title=esc(ch.title), id=ch.id, added_by=esc(adder.display) if adder else (ch.added_by or "?"), owner=esc(owner.display) if owner else (ch.owner_user_id or "?")))
        rows.append([(f"{t(lang, 'btn_activate')} · {esc(ch.title)[:20]}", Act(a=A_ACTIVATE, c=ch.id).pack()), (t(lang, "btn_decline"), Act(a=A_DECLINE, c=ch.id).pack())])
    text = compose(t(lang, "pend_title"), *(blocks or [t(lang, "pend_empty")]))
    rows.append(pager(lang, screen=S_PENDING, channel=0, arg="", page=page, total_pages=total))
    rows.append(nav(lang, back=Nav(s=S_SYSTEM).pack()))
    return text, kb(rows)


async def all_channels_screen(ctx: Services, s: AsyncSession, lang: str, page: int):
    chans = await ch_repo.list_all(s)
    items, page, total = paginate(chans, page, 8)
    lines = [f"{channel_state(lang, c)} · {esc(c.title)} · <code>{c.id}</code>" for c in items]
    text = compose(t(lang, "sysc_title"), (None, lines) if lines else t(lang, "chs_empty"))
    rows = [[(f"{channel_state(lang, c)[0]} {esc(c.title)[:36]}", Nav(s=S_DASH, c=c.id).pack())] for c in items]
    rows.append(pager(lang, screen=S_ALL_CHANNELS, channel=0, arg="", page=page, total_pages=total))
    rows.append(nav(lang, back=Nav(s=S_SYSTEM).pack()))
    return text, kb(rows)


async def sysadmins_screen(ctx: Services, s: AsyncSession, lang: str):
    owner = await user_repo.get(s, ctx.config.system_owner_id)
    admins = await user_repo.list_by_role(s, "admin")
    lines = [f"{G.SPARK} {esc(owner.display) if owner else ctx.config.system_owner_id} · {t(lang, 'sysa_owner')}"]
    rows: list[list[tuple[str, str]]] = []
    for u in admins:
        lines.append(f"{G.ACTIVE} {esc(u.display)} · {t(lang, 'sysa_admin')}")
        rows.append([(f"{t(lang, 'btn_remove')} · {esc(u.display)[:24]}", Act(a=A_SYSADMIN_DEL, t=str(u.id)).pack())])
    text = compose(t(lang, "sysa_title"), t(lang, "sysa_hint"), (None, lines))
    rows.append([(t(lang, "btn_add_sysadmin"), Act(a=A_SYSADMIN_ADD).pack())])
    rows.append(nav(lang, back=Nav(s=S_SYSTEM).pack()))
    return text, kb(rows)


async def health_screen(ctx: Services, s: AsyncSession, lang: str):
    db_ok = await ctx.db.healthy()
    mod = ctx.moderation.status()
    sessions = await shield_repo.list_active_sessions(s)
    lines = [
        f"{G.ACTIVE if db_ok else G.ATTENTION} {t(lang, 'hlth_db')} · {t(lang, 'hlth_ok') if db_ok else t(lang, 'hlth_fail')}",
        f"{t(lang, 'hlth_uptime')} · {humanize_duration(int((utcnow() - ctx.started_at).total_seconds()), lang)}",
        f"{t(lang, 'hlth_sessions')} · {len(sessions)}",
        f"{t(lang, 'hlth_media_groups')} · {len(ctx.media_groups)}",
    ]
    mod_lines = []
    if mod["enabled"]:
        mod_lines.append(f"{G.ACTIVE if not mod['budget_exhausted'] else G.ATTENTION} {t(lang, 'hlth_requests')} · {mod['requests_today']} / {mod['budget']}")
        if mod["budget_exhausted"]:
            mod_lines.append(f"{G.ATTENTION} {t(lang, 'hlth_budget_exhausted')}")
        mod_lines.append(f"{t(lang, 'hlth_chain')}\n" + "\n".join(f"  {G.OFF if m in mod['cooling'] else G.ACTIVE} <code>{esc(m)}</code>" + (f" · {t(lang, 'hlth_cooling')} {mod['cooling'][m]}s" if m in mod["cooling"] else "") for m in mod["chain"]))
        if mod["last_model"]:
            mod_lines.append(f"{t(lang, 'hlth_last_model')} · <code>{esc(mod['last_model'])}</code>")
        if mod["last_error"]:
            mod_lines.append(f"{t(lang, 'hlth_last_error')} · <code>{esc(mod['last_error'][:120])}</code>")
        key = await ctx.moderation.key_info()
        if key:
            mod_lines.append(f"{t(lang, 'hlth_key')} · " + t(lang, "hlth_key_line", usage=key.get("usage", "?"), limit=key.get("limit", "∞") or "∞", free_today=key.get("free_model_daily_requests", key.get("usage_daily", "?"))))
    else:
        mod_lines.append(f"{G.OFF} {t(lang, 'sys_moderation_off')}")
    text = compose(t(lang, "hlth_title"), (None, lines), (t(lang, "hlth_moderation"), mod_lines))
    return text, kb([nav(lang, back=Nav(s=S_SYSTEM).pack(), refresh=Nav(s=S_HEALTH).pack())])


@router.callback_query(Nav.filter(F.s.in_({S_SYSTEM, S_PENDING, S_ALL_CHANNELS, S_SYS_ADMINS, S_HEALTH})))
async def nav_system(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    if not await guard_system(cb, ctx, s, user, lang):
        return
    if callback_data.s == S_SYSTEM:
        text, markup = await system_screen(ctx, s, lang)
    elif callback_data.s == S_PENDING:
        text, markup = await pending_screen(ctx, s, lang, callback_data.p)
    elif callback_data.s == S_ALL_CHANNELS:
        text, markup = await all_channels_screen(ctx, s, lang, callback_data.p)
    elif callback_data.s == S_SYS_ADMINS:
        text, markup = await sysadmins_screen(ctx, s, lang)
    else:
        text, markup = await health_screen(ctx, s, lang)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Act.filter(F.a.in_({A_ACTIVATE, A_DECLINE})))
async def act_activation(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    if not await guard_system(cb, ctx, s, user, lang):
        return
    ch = await ch_repo.get(s, callback_data.c)
    if ch is None:
        await toast(cb, t(lang, "toast_nothing"))
        return
    if callback_data.a == A_ACTIVATE:
        if ch.status == "active":
            await toast(cb, t(lang, "toast_nothing"))
            return
        await show(cb, t(lang, "working"))
        ch, sync = await ctx.channels.activate(s, ch.id, by=user.id)
        managed = sum(1 for a in sync.admins if a.status == "active")
        unmanaged = sum(1 for a in sync.admins if a.status == "unmanaged")
        await ctx.notifier.channel_activated(s, ch, managed=managed, unmanaged=unmanaged)
        msg = t(lang, "activated_ok")
    else:
        await ctx.channels.set_status(s, ch.id, "revoked", by=user.id, action="channel.declined")
        await ctx.notifier.channel_declined(s, ch)
        msg = t(lang, "declined_ok")
    text, markup = await pending_screen(ctx, s, lang, 0)
    await show(cb, text, markup)
    await toast(cb, msg)


@router.callback_query(Act.filter(F.a == A_SYSADMIN_ADD))
async def act_sysadmin_add(cb: CallbackQuery, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    if not ctx.access.is_system_owner(user.id):
        await toast(cb, t(lang, "toast_not_permitted"), alert=True)
        return
    await state.set_state(Input.sysadmin_user)
    await cb.message.answer(t(lang, "sysa_add_prompt"), reply_markup=cancel_kb(lang))
    await cb.answer()


@router.message(Input.sysadmin_user, F.chat.type == "private")
async def input_sysadmin(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    if not ctx.access.is_system_owner(user.id):
        await state.clear()
        return
    ref = resolve_user_ref(message)
    if ref is None or ref.is_bot:
        await message.answer(t(lang, "adda_invalid"))
        return
    await user_repo.ensure(s, ref.user_id, username=ref.username, first_name=ref.name or None)
    await ctx.access.grant_system_admin(s, ref.user_id)
    await audit.log(s, "system.admin_added", actor=user.id, target_type="user", target_id=ref.user_id)
    await state.clear()
    text, markup = await sysadmins_screen(ctx, s, lang)
    await message.answer(t(lang, "sysa_added"))
    await message.answer(text, reply_markup=markup)


@router.callback_query(Act.filter(F.a == A_SYSADMIN_DEL))
async def act_sysadmin_del(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    if not ctx.access.is_system_owner(user.id):
        await toast(cb, t(lang, "toast_not_permitted"), alert=True)
        return
    uid = int(callback_data.t) if callback_data.t.isdigit() else 0
    await ctx.access.revoke_system_admin(s, uid)
    await audit.log(s, "system.admin_removed", actor=user.id, target_type="user", target_id=uid)
    text, markup = await sysadmins_screen(ctx, s, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "sysa_removed"))
