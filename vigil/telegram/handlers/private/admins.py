"""Administrators: list, detail, contextual actions, and the add flow."""

from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    KeyboardButtonRequestUsers,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core import glyphs as G
from vigil.core.errors import AdminNotManaged, BotRightsMissing, TelegramFailure
from vigil.core.rights import PRESETS, enabled_rights, normalize_rights
from vigil.core.timeutil import fmt_datetime, humanize_ago, utcnow
from vigil.db.models import Admin, Channel, User
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import snapshots as snap_repo
from vigil.db.repo import violations as vio_repo
from vigil.services.context import Services
from vigil.telegram.callbacks import (
    A_ADD_CONFIRM,
    A_ADD_PRESET,
    A_ADMIN_EXEMPT,
    A_ADMIN_REMOVE,
    A_ADMIN_RESET,
    A_ADMIN_RESTORE,
    A_ADMIN_SUSPEND,
    A_ADMIN_SYNC,
    A_ADOPT,
    A_CANCEL,
    S_ADD_ADMIN,
    S_ADMIN,
    S_ADMINS,
    S_DASH,
    S_VIOLATIONS,
    Act,
    Nav,
)
from vigil.telegram.handlers.private.common import (
    Input,
    guard_channel,
    resolve_user_ref,
    right_labels,
)
from vigil.telegram.ui.screens import compose, kb, nav, pager, paginate, show, toast
from vigil.telegram.ui.texts import esc, t

router = Router(name="private_admins")

STATUS_GLYPH = {
    "active": G.ACTIVE,
    "suspended": G.OFF,
    "shielded": G.SHIELDED,
    "unmanaged": G.ATTENTION,
    "removed": G.OFF,
    "owner": G.SPARK,
}


def _status(lang: str, a: Admin) -> str:
    return f"{STATUS_GLYPH.get(a.status, G.WAITING)} {t(lang, 'st_' + a.status)}"


async def _visible_admins(s: AsyncSession, ch: Channel) -> list[Admin]:
    admins = await admin_repo.list_for_channel(s, ch.id, statuses=("owner", "active", "shielded", "suspended", "unmanaged", "removed"))
    cutoff = utcnow() - timedelta(hours=24)
    order = {"owner": 0, "active": 1, "shielded": 2, "suspended": 3, "unmanaged": 4, "removed": 5}
    out = [a for a in admins if a.status != "removed" or (a.demoted_at and a.demoted_at >= cutoff and a.rights)]
    return sorted(out, key=lambda a: (order.get(a.status, 9), a.full_name.lower()))


async def admins_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str, page: int):
    admins = await _visible_admins(s, ch)
    items, page, total = paginate(admins, page, 8)
    if not admins:
        text = compose(t(lang, "adm_title"), t(lang, "adm_empty"))
    else:
        text = compose(f"{t(lang, 'adm_title')} {G.DOT} {esc(ch.title)}", t(lang, "adm_count", n=len(admins)))
    rows = [[(f"{STATUS_GLYPH.get(a.status, G.WAITING)} {esc(a.display)[:32]}", Nav(s=S_ADMIN, c=ch.id, a=str(a.id)).pack())] for a in items]
    rows.append(pager(lang, screen=S_ADMINS, channel=ch.id, arg="", page=page, total_pages=total))
    rows.append([(t(lang, "btn_add_admin"), Nav(s=S_ADD_ADMIN, c=ch.id).pack()), (t(lang, "btn_sync"), Act(a=A_ADMIN_SYNC, c=ch.id).pack())])
    rows.append(nav(lang, back=Nav(s=S_DASH, c=ch.id).pack()))
    return text, kb(rows)


async def admin_screen(ctx: Services, s: AsyncSession, ch: Channel, a: Admin, lang: str):
    rights = enabled_rights(normalize_rights(a.rights))
    info = [f"{esc(a.display)}" + (f" · @{esc(a.username)}" if a.username else ""), f"{t(lang, 'id')} · <code>{a.user_id}</code>"]
    if a.custom_title:
        info.append(f"{t(lang, 'adm_title_label')} · {esc(a.custom_title)}")
    status_lines = [_status(lang, a)]
    if a.status == "owner":
        status_lines.append(t(lang, "adm_owner_note"))
    elif a.status == "unmanaged":
        status_lines.append(t(lang, "adm_unmanaged_hint"))
    else:
        if a.managed_by_bot:
            status_lines.append(f"{G.ACTIVE} {t(lang, 'adm_managed')}")
        if a.shield_exempt:
            status_lines.append(f"{G.WAITING} {t(lang, 'adm_exempt')}")
        if a.demote_reason and a.status in ("suspended", "shielded", "removed"):
            status_lines.append(f"{t(lang, 'reason')} · {esc(a.demote_reason)}")
        if a.promoted_at and a.status == "active":
            status_lines.append(f"{t(lang, 'adm_since')} · {fmt_datetime(a.promoted_at, ch.timezone)}")

    vio_lines = [t(lang, "adm_no_violations")]
    recent = await vio_repo.list_for_admin(s, ch.id, a.user_id, limit=1)
    if recent:
        v = recent[0]
        vio_lines = [
            f"{a.violations_count or len(recent)} · {t(lang, 'adm_last_violation')} · {humanize_ago(v.created_at, lang)}",
            f"{t(lang, 'kind_' + v.kind)} · {esc(v.detail or '')[:60]}",
        ]
    text = compose(
        t(lang, "adm_detail_title"),
        (None, info),
        (t(lang, "adm_status"), status_lines),
        (t(lang, "adm_rights"), [right_labels(lang, rights) if rights else t(lang, "adm_no_rights")]),
        (t(lang, "adm_violations"), vio_lines),
    )
    rows: list[list[tuple[str, str]]] = []
    aid = str(a.id)
    if a.status == "active":
        rows.append([(t(lang, "btn_suspend"), Act(a=A_ADMIN_SUSPEND, c=ch.id, t=aid).pack()),
                     (t(lang, "btn_exempt_off" if a.shield_exempt else "btn_exempt_on"), Act(a=A_ADMIN_EXEMPT, c=ch.id, t=aid).pack())])
        rows.append([(t(lang, "btn_violations"), Nav(s=S_VIOLATIONS, c=ch.id, a=str(a.user_id)).pack()),
                     (t(lang, "btn_remove"), Act(a=A_ADMIN_REMOVE, c=ch.id, t=aid).pack())])
    elif a.status in ("suspended", "shielded"):
        rows.append([(t(lang, "btn_restore"), Act(a=A_ADMIN_RESTORE, c=ch.id, t=aid).pack()),
                     (t(lang, "btn_reset"), Act(a=A_ADMIN_RESET, c=ch.id, t=aid).pack())])
        rows.append([(t(lang, "btn_violations"), Nav(s=S_VIOLATIONS, c=ch.id, a=str(a.user_id)).pack()),
                     (t(lang, "btn_remove"), Act(a=A_ADMIN_REMOVE, c=ch.id, t=aid).pack())])
    elif a.status in ("unmanaged", "removed"):
        rows.append([(t(lang, "btn_adopt"), Act(a=A_ADOPT, c=ch.id, t=aid).pack())])
        rows.append([(t(lang, "btn_violations"), Nav(s=S_VIOLATIONS, c=ch.id, a=str(a.user_id)).pack())])
    else:
        rows.append([(t(lang, "btn_violations"), Nav(s=S_VIOLATIONS, c=ch.id, a=str(a.user_id)).pack())])
    rows.append(nav(lang, back=Nav(s=S_ADMINS, c=ch.id).pack(), refresh=Nav(s=S_ADMIN, c=ch.id, a=aid).pack()))
    return text, kb(rows)


async def _load(cb: CallbackQuery, ctx: Services, s: AsyncSession, user: User, channel_id: int, admin_id: str, lang: str) -> tuple[Channel, Admin] | None:
    ch = await guard_channel(cb, ctx, s, user, channel_id, lang)
    if ch is None:
        return None
    a = await admin_repo.get(s, int(admin_id)) if admin_id.isdigit() else None
    if a is None or a.channel_id != ch.id:
        await toast(cb, t(lang, "toast_nothing"))
        return None
    return ch, a


# ── navigation ─────────────────────────────────────────────────

@router.callback_query(Nav.filter(F.s == S_ADMINS))
async def nav_admins(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    text, markup = await admins_screen(ctx, s, ch, lang, callback_data.p)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Nav.filter(F.s == S_ADMIN))
async def nav_admin(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    loaded = await _load(cb, ctx, s, user, callback_data.c, callback_data.a, lang)
    if loaded is None:
        return
    ch, a = loaded
    text, markup = await admin_screen(ctx, s, ch, a, lang)
    await show(cb, text, markup)
    await cb.answer()


# ── actions ────────────────────────────────────────────────────

@router.callback_query(Act.filter(F.a == A_ADMIN_SYNC))
async def act_sync(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    result = await ctx.channels.sync_admins(s, ch)
    text, markup = await admins_screen(ctx, s, ch, lang, 0)
    await show(cb, text, markup)
    await toast(cb, t(lang, "toast_synced") if not result.error else t(lang, "err_telegram", error=result.error), alert=bool(result.error))


@router.callback_query(Act.filter(F.a.in_({A_ADMIN_SUSPEND, A_ADMIN_REMOVE})))
async def act_suspend_or_remove(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    loaded = await _load(cb, ctx, s, user, callback_data.c, callback_data.t, lang)
    if loaded is None:
        return
    ch, a = loaded
    removing = callback_data.a == A_ADMIN_REMOVE
    if callback_data.v != "ok":
        key = "confirm_remove" if removing else "confirm_suspend"
        text = compose(t(lang, "adm_detail_title"), t(lang, key, name=esc(a.display)))
        markup = kb([
            [(t(lang, "confirm"), Act(a=callback_data.a, c=ch.id, t=str(a.id), v="ok").pack())],
            [(t(lang, "cancel"), Nav(s=S_ADMIN, c=ch.id, a=str(a.id)).pack())],
        ])
        await show(cb, text, markup)
        await cb.answer()
        return
    try:
        if removing:
            await ctx.admins.remove(s, ch, a, by=user.id)
            msg = t(lang, "removed_ok")
        else:
            await ctx.admins.demote(s, ch, a, reason=t("en", "suspend_reason_manual"), snapshot_reason="manual", by=user.id)
            msg = t(lang, "suspended_ok")
    except AdminNotManaged:
        msg = t(lang, "err_not_managed")
    except BotRightsMissing as e:
        msg = t(lang, "err_bot_rights", rights=right_labels(lang, e.missing))
    except TelegramFailure as e:
        msg = t(lang, "err_telegram", error=esc(str(e)))
    a = await admin_repo.get(s, a.id) or a
    text, markup = await admin_screen(ctx, s, ch, a, lang)
    await show(cb, text, markup)
    await toast(cb, msg, alert=len(msg) > 40)


@router.callback_query(Act.filter(F.a == A_ADMIN_RESTORE))
async def act_restore(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    loaded = await _load(cb, ctx, s, user, callback_data.c, callback_data.t, lang)
    if loaded is None:
        return
    ch, a = loaded
    snap = await snap_repo.latest_unrestored(s, ch.id, a.user_id) or await snap_repo.latest_any(s, ch.id, a.user_id)
    try:
        outcome = await ctx.admins.restore(s, ch, a.user_id, snap, by=user.id)
    except BotRightsMissing as e:
        await toast(cb, t(lang, "err_bot_rights", rights=right_labels(lang, e.missing)), alert=True)
        return
    if outcome.ok:
        msg = t(lang, "restored_ok")
        if outcome.dropped_rights:
            msg += "\n" + t(lang, "restored_dropped", rights=right_labels(lang, outcome.dropped_rights))
        if outcome.custom_title:
            msg += "\n" + t(lang, "restored_title_hint", title=outcome.custom_title)
    else:
        msg = t(lang, "restore_failed", error=esc(outcome.error or ""))
    a = await admin_repo.get(s, a.id) or a
    text, markup = await admin_screen(ctx, s, ch, a, lang)
    await show(cb, text, markup)
    await toast(cb, msg, alert=len(msg) > 40)


@router.callback_query(Act.filter(F.a == A_ADMIN_EXEMPT))
async def act_exempt(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    loaded = await _load(cb, ctx, s, user, callback_data.c, callback_data.t, lang)
    if loaded is None:
        return
    ch, a = loaded
    await ctx.admins.set_exempt(s, ch, a, not a.shield_exempt, by=user.id)
    text, markup = await admin_screen(ctx, s, ch, a, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "exempt_on_ok" if a.shield_exempt else "exempt_off_ok"))


@router.callback_query(Act.filter(F.a == A_ADMIN_RESET))
async def act_reset(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    loaded = await _load(cb, ctx, s, user, callback_data.c, callback_data.t, lang)
    if loaded is None:
        return
    ch, a = loaded
    await ctx.admins.reset_status(s, ch, a, by=user.id)
    text, markup = await admin_screen(ctx, s, ch, a, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "reset_ok"))


@router.callback_query(Act.filter(F.a == A_ADOPT))
async def act_adopt(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    loaded = await _load(cb, ctx, s, user, callback_data.c, callback_data.t, lang)
    if loaded is None:
        return
    ch, a = loaded
    rights = normalize_rights(a.rights) if a.rights and any(a.rights.values()) else dict(PRESETS["publisher"])
    try:
        await ctx.admins.promote(s, ch, a.user_id, rights, by=user.id, username=a.username, full_name=a.full_name)
        msg = t(lang, "adda_done", name=esc(a.display))
    except AdminNotManaged:
        msg = t(lang, "err_not_managed")
    except BotRightsMissing as e:
        msg = t(lang, "err_bot_rights", rights=right_labels(lang, e.missing))
    except TelegramFailure as e:
        msg = t(lang, "adda_failed", error=esc(str(e)))
    a = await admin_repo.get(s, a.id) or a
    text, markup = await admin_screen(ctx, s, ch, a, lang)
    await show(cb, text, markup)
    await toast(cb, msg, alert=True)


# ── add administrator flow ─────────────────────────────────────

def _pick_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "adda_pick_button"), request_users=KeyboardButtonRequestUsers(request_id=7, user_is_bot=False, max_quantity=1, request_name=True, request_username=True))],
            [KeyboardButton(text=t(lang, "cancel"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.callback_query(Nav.filter(F.s == S_ADD_ADMIN))
async def nav_add_admin(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    await state.set_state(Input.admin_user)
    await state.update_data(c=ch.id)
    await cb.message.answer(compose(t(lang, "adda_title"), t(lang, "adda_prompt")), reply_markup=_pick_keyboard(lang))
    await cb.answer()


@router.message(Input.admin_user, F.chat.type == "private")
async def input_admin_user(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    if (message.text or "").strip().lower() in (t(lang, "cancel").lower(), "/cancel", "cancel"):
        await state.clear()
        await message.answer(t(lang, "input_cancelled"), reply_markup=ReplyKeyboardRemove())
        return
    ch = await guard_channel(message, ctx, s, user, int(data.get("c", 0)), lang)
    if ch is None:
        await state.clear()
        return
    ref = resolve_user_ref(message)
    if ref is None:
        await message.answer(t(lang, "adda_invalid"))
        return
    if ref.is_bot:
        await message.answer(t(lang, "adda_is_bot"))
        return
    existing = await admin_repo.get_by_user(s, ch.id, ref.user_id)
    if existing is not None and existing.status in ("active", "owner", "unmanaged"):
        await message.answer(t(lang, "adda_already", name=esc(existing.display)), reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
    name = ref.name or (f"@{ref.username}" if ref.username else str(ref.user_id))
    await state.update_data(uid=ref.user_id, uname=ref.username or "", name=name)
    await message.answer(t(lang, "adda_preset_hint"), reply_markup=ReplyKeyboardRemove())
    rows = [[(f"{t(lang, 'preset_' + p)} · {t(lang, 'preset_' + p + '_desc')}", Act(a=A_ADD_PRESET, c=ch.id, t=p).pack())] for p in ("publisher", "editor", "moderator", "full")]
    rows.append([(t(lang, "cancel"), Act(a=A_CANCEL).pack())])
    await message.answer(compose(t(lang, "adda_preset_title", name=esc(name))), reply_markup=kb(rows))


@router.callback_query(Act.filter(F.a == A_ADD_PRESET))
async def act_add_preset(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    if not data.get("uid"):
        await toast(cb, t(lang, "toast_error"), alert=True)
        return
    preset = callback_data.t if callback_data.t in PRESETS else "publisher"
    rights = enabled_rights(PRESETS[preset])
    text = compose(t(lang, "adda_title"), t(lang, "adda_confirm", name=esc(data["name"]), preset=t(lang, "preset_" + preset), rights=right_labels(lang, rights)))
    markup = kb([
        [(t(lang, "confirm"), Act(a=A_ADD_CONFIRM, c=ch.id, t=preset).pack())],
        [(t(lang, "cancel"), Act(a=A_CANCEL).pack())],
    ])
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Act.filter(F.a == A_ADD_CONFIRM))
async def act_add_confirm(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    if not data.get("uid"):
        await toast(cb, t(lang, "toast_error"), alert=True)
        return
    preset = callback_data.t if callback_data.t in PRESETS else "publisher"
    await show(cb, t(lang, "working"))
    try:
        admin, dropped = await ctx.admins.promote(s, ch, int(data["uid"]), PRESETS[preset], by=user.id, username=data.get("uname") or None, full_name=data.get("name", ""))
        lines = [t(lang, "adda_done", name=esc(admin.display))]
        if dropped:
            lines.append(t(lang, "adda_dropped", rights=right_labels(lang, dropped)))
        text = compose(t(lang, "adda_title"), *lines)
        markup = kb([[(t(lang, "btn_view_admin"), Nav(s=S_ADMIN, c=ch.id, a=str(admin.id)).pack())], nav(lang, back=Nav(s=S_ADMINS, c=ch.id).pack())])
    except AdminNotManaged as e:
        text = compose(t(lang, "adda_title"), t(lang, "adda_failed", error=esc(str(e))), t(lang, "adda_hint_join"))
        markup = kb([nav(lang, back=Nav(s=S_ADMINS, c=ch.id).pack())])
    except BotRightsMissing as e:
        text = compose(t(lang, "adda_title"), t(lang, "err_bot_rights", rights=right_labels(lang, e.missing)))
        markup = kb([nav(lang, back=Nav(s=S_ADMINS, c=ch.id).pack())])
    except TelegramFailure as e:
        text = compose(t(lang, "adda_title"), t(lang, "adda_failed", error=esc(str(e))), t(lang, "adda_hint_join"))
        markup = kb([nav(lang, back=Nav(s=S_ADMINS, c=ch.id).pack())])
    await state.clear()
    await show(cb, text, markup)
    await cb.answer()
