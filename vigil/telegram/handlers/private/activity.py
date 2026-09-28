"""Activity log, violations list and detail, one-tap restore from cards."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core import glyphs as G
from vigil.core.errors import BotRightsMissing
from vigil.core.timeutil import fmt_clock, fmt_datetime, humanize_ago
from vigil.db.models import Channel, User
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import audit as audit_repo
from vigil.db.repo import snapshots as snap_repo
from vigil.db.repo import violations as vio_repo
from vigil.services.context import Services
from vigil.telegram.callbacks import (
    A_RESTORE_VIOLATION,
    S_ACTIVITY,
    S_ADMIN,
    S_DASH,
    S_VIOLATION,
    S_VIOLATIONS,
    Act,
    Nav,
)
from vigil.telegram.handlers.private.common import audit_label, guard_channel, right_labels
from vigil.telegram.ui import cards
from vigil.telegram.ui.screens import compose, kb, nav, pager, paginate, show, toast
from vigil.telegram.ui.texts import esc, t

router = Router(name="private_activity")

FILTERS = {"": None, "v": "violation", "a": "admin.", "s": "shield.", "c": "channel."}
FILTER_LABEL = {"": "flt_all", "v": "flt_violations", "a": "flt_admins", "s": "flt_shield", "c": "flt_channel"}
PER_PAGE = 10


async def activity_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str, flt: str, page: int):
    prefix = FILTERS.get(flt)
    total_n = await audit_repo.count(s, ch.id, prefix)
    total_pages = max(1, (total_n + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    entries = await audit_repo.list_entries(s, channel_id=ch.id, limit=PER_PAGE, offset=page * PER_PAGE, action_prefix=prefix)
    names: dict[int, str] = {}
    lines: list[str] = []
    for e in entries:
        det = e.details or {}
        who = ""
        if e.target_type == "user" and e.target_id and e.target_id.isdigit():
            uid = int(e.target_id)
            if uid not in names:
                a = await admin_repo.get_by_user(s, ch.id, uid)
                names[uid] = a.display if a else str(uid)
            who = names[uid]
        extra = det.get("kind") or det.get("reason") or det.get("key") or ""
        bits = [fmt_datetime(e.created_at, ch.timezone), audit_label(lang, e.action)]
        if who:
            bits.append(esc(who))
        if extra:
            bits.append(esc(str(extra))[:40])
        lines.append(f"{G.DOT} " + " · ".join(bits))
    text = compose(f"{t(lang, 'act_title')} {G.DOT} {esc(ch.title)}", (None, lines) if lines else t(lang, "act_empty"))
    frow = [(f"{'●' if k == flt else '○'} {t(lang, v)}", Nav(s=S_ACTIVITY, c=ch.id, a=k).pack()) for k, v in FILTER_LABEL.items()]
    rows = [frow[:3], frow[3:], pager(lang, screen=S_ACTIVITY, channel=ch.id, arg=flt, page=page, total_pages=total_pages), [(t(lang, "vio_title"), Nav(s=S_VIOLATIONS, c=ch.id).pack())], nav(lang, back=Nav(s=S_DASH, c=ch.id).pack(), refresh=Nav(s=S_ACTIVITY, c=ch.id, a=flt, p=page).pack())]
    return text, kb(rows)


async def violations_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str, user_filter: str, page: int):
    if user_filter.isdigit():
        items_all = await vio_repo.list_for_admin(s, ch.id, int(user_filter), limit=100)
    else:
        items_all = await vio_repo.list_for_channel(s, ch.id, limit=200)
    items, page, total = paginate(items_all, page, 8)
    text = compose(f"{t(lang, 'vio_title')} {G.DOT} {esc(ch.title)}", t(lang, "vio_empty") if not items_all else f"{len(items_all)}")
    rows = [[(t(lang, "vio_row", time=fmt_clock(v.created_at, ch.timezone), name=esc(v.display_name or "?")[:18], kind=t(lang, "kind_" + v.kind)), Nav(s=S_VIOLATION, c=ch.id, a=str(v.id)).pack())] for v in items]
    rows.append(pager(lang, screen=S_VIOLATIONS, channel=ch.id, arg=user_filter, page=page, total_pages=total))
    rows.append(nav(lang, back=Nav(s=S_ACTIVITY, c=ch.id).pack()))
    return text, kb(rows)


async def violation_screen(ctx: Services, s: AsyncSession, ch: Channel, v, lang: str):  # noqa: ANN001
    admin = await admin_repo.get(s, v.admin_id) if v.admin_id else None
    lines = [
        f"{t(lang, 'vio_admin')} · {esc(v.display_name or t(lang, 'card_unsigned_name'))}" + (f" · @{esc(v.username)}" if v.username else ""),
        f"{t(lang, 'vio_kind')} · {t(lang, 'kind_' + v.kind)}",
        f"{t(lang, 'vio_rule')} · <code>{esc(v.rule)}</code>",
    ]
    if v.detail:
        lines.append(f"{t(lang, 'reason')} · {esc(v.detail)}")
    lines.append(f"{t(lang, 'vio_action')} · {esc(v.action)}")
    lines.append(f"{t(lang, 'vio_post')} · #{v.message_id} · {fmt_datetime(v.created_at, ch.timezone)}")
    if v.excerpt:
        lines.append("")
        lines.append(f"<b>{t(lang, 'vio_excerpt')}</b>\n<i>{esc(v.excerpt[:300])}</i>")
    api = v.api_result or {}
    if api and api.get("model"):
        lines.append("")
        lines.append(f"<b>{t(lang, 'vio_api')}</b>\n" + t(lang, "vio_api_line", model=esc(api.get("model", "")), category=esc(api.get("category", "")), severity=esc(api.get("severity", ""))) + (f"\n<i>{esc(api.get('reason', ''))}</i>" if api.get("reason") else ""))
    if v.restored_at:
        lines.append("")
        lines.append(f"{G.ACTIVE} {t(lang, 'vio_restored', when=humanize_ago(v.restored_at, lang))}")
    text = compose(t(lang, "vio_detail_title"), (None, lines))
    rows: list[list[tuple[str, str]]] = []
    if "demoted" in (v.action or "") and not v.restored_at and admin is not None and admin.status in ("suspended", "shielded"):
        rows.append([(t(lang, "btn_restore_admin"), Act(a=A_RESTORE_VIOLATION, c=ch.id, t=str(v.id)).pack())])
    if admin is not None:
        rows.append([(t(lang, "btn_view_admin"), Nav(s=S_ADMIN, c=ch.id, a=str(admin.id)).pack())])
    rows.append(nav(lang, back=Nav(s=S_VIOLATIONS, c=ch.id).pack()))
    return text, kb(rows)


@router.callback_query(Nav.filter(F.s == S_ACTIVITY))
async def nav_activity(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    text, markup = await activity_screen(ctx, s, ch, lang, callback_data.a, callback_data.p)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Nav.filter(F.s == S_VIOLATIONS))
async def nav_violations(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    text, markup = await violations_screen(ctx, s, ch, lang, callback_data.a, callback_data.p)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Nav.filter(F.s == S_VIOLATION))
async def nav_violation(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    v = await vio_repo.get(s, int(callback_data.a)) if callback_data.a.isdigit() else None
    if v is None or v.channel_id != ch.id:
        await toast(cb, t(lang, "toast_nothing"))
        return
    text, markup = await violation_screen(ctx, s, ch, v, lang)
    # Opened from a notification card → keep the card, open details as a new message.
    from_card = bool(cb.message and cb.message.reply_markup and any(
        (b.callback_data or "").startswith("x:rsv") for r in cb.message.reply_markup.inline_keyboard for b in r
    ))
    await show(cb, text, markup, new=from_card)
    await cb.answer()


@router.callback_query(Act.filter(F.a == A_RESTORE_VIOLATION))
async def act_restore_violation(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    v = await vio_repo.get(s, int(callback_data.t)) if callback_data.t.isdigit() else None
    if v is None or v.channel_id != ch.id or v.user_id is None:
        await toast(cb, t(lang, "toast_nothing"))
        return
    if v.restored_at:
        await toast(cb, t(lang, "toast_nothing"))
        return
    snap = await snap_repo.get(s, v.snapshot_id) if v.snapshot_id else None
    if snap is None:
        snap = await snap_repo.latest_unrestored(s, ch.id, v.user_id) or await snap_repo.latest_any(s, ch.id, v.user_id)
    try:
        outcome = await ctx.admins.restore(s, ch, v.user_id, snap, by=user.id, source="violation_card")
    except BotRightsMissing as e:
        await toast(cb, t(lang, "err_bot_rights", rights=right_labels(lang, e.missing)), alert=True)
        return
    if not outcome.ok:
        await toast(cb, t(lang, "restore_failed", error=outcome.error or ""), alert=True)
        return
    await vio_repo.mark_restored(s, v, user.id)
    admin = await admin_repo.get(s, v.admin_id) if v.admin_id else None
    msg = t(lang, "restored_ok")
    if outcome.dropped_rights:
        msg += "\n" + t(lang, "restored_dropped", rights=right_labels(lang, outcome.dropped_rights))
    if outcome.custom_title:
        msg += "\n" + t(lang, "restored_title_hint", title=outcome.custom_title)
    text, markup = cards.violation_card(
        lang, ch, v, admin, attribution_status="ok", signature=v.display_name,
        demoted=True, deleted="deleted" in (v.action or ""), could_not=None, restored_by=user.display,
    )
    await show(cb, text, markup)
    await toast(cb, msg, alert=len(msg) > 40)
