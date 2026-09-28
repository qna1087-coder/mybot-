"""Shield Mode: start / stop, schedules, exemptions, history."""

from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core import glyphs as G
from vigil.core.errors import BotRightsMissing
from vigil.core.timeutil import fmt_clock, fmt_datetime, parse_duration, parse_hhmm, utcnow
from vigil.db.models import Channel, User
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import audit
from vigil.db.repo import shield as repo
from vigil.services.context import Services
from vigil.services.shield.schedules import ALL_DAYS, describe_days
from vigil.telegram.callbacks import (
    A_EXEMPT_TOGGLE,
    A_RETRY_SHIELD,
    A_SCHEDULE_ADD,
    A_SCHEDULE_DAY,
    A_SCHEDULE_DEL,
    A_SCHEDULE_TOGGLE,
    A_SHIELD_START,
    A_SHIELD_STOP,
    S_DASH,
    S_EXEMPT,
    S_HISTORY,
    S_SCHEDULE,
    S_SCHEDULES,
    S_SHIELD,
    S_SHIELD_START,
    Act,
    Nav,
)
from vigil.telegram.handlers.private.common import Input, cancel_kb, guard_channel, right_labels
from vigil.telegram.ui.screens import compose, kb, nav, show, toast
from vigil.telegram.ui.texts import esc, t

router = Router(name="private_shield")


def _day_labels(lang: str) -> list[str]:
    return [t(lang, f"day_{i}") for i in range(7)] + [t(lang, "sch_daily")]


async def shield_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str):
    st = await ctx.shield.status(s, ch)
    lines: list[str] = []
    if st.session is not None:
        sess = st.session
        if sess.status == "ending":
            lines.append(f"{G.SHIELDED} {t(lang, 'shd_ending')}")
        elif sess.ends_at:
            lines.append(f"{G.SHIELDED} {t(lang, 'shd_active_until', until=fmt_datetime(sess.ends_at, ch.timezone))}")
        else:
            lines.append(f"{G.SHIELDED} {t(lang, 'shd_active_manual')}")
        lines.append(t(lang, "shd_since", since=fmt_datetime(sess.started_at, ch.timezone)))
        lines.append(t(lang, "shd_members", suspended=st.suspended, failed=st.failed))
    else:
        lines.append(f"{G.OFF} {t(lang, 'shd_offline')}")
    detail = [t(lang, "shd_exempt", n=st.exempt), t(lang, "shd_schedules", n=st.schedules)]
    if st.next_start:
        detail.append(t(lang, "shd_next", when=f"{fmt_datetime(st.next_start, ch.timezone)} → {fmt_clock(st.next_end, ch.timezone)}"))
    else:
        detail.append(t(lang, "shd_no_next"))
    text = compose(f"{t(lang, 'shd_title')} {G.DOT} {esc(ch.title)}", t(lang, "shd_intro"), (t(lang, "shd_state"), lines), (None, detail), footer=t(lang, "tz_line", tz=ch.timezone))
    rows: list[list[tuple[str, str]]] = []
    if st.session is not None:
        rows.append([(t(lang, "btn_stop"), Act(a=A_SHIELD_STOP, c=ch.id).pack())])
    else:
        rows.append([(t(lang, "btn_start"), Nav(s=S_SHIELD_START, c=ch.id).pack())])
    rows.append([(t(lang, "btn_schedules"), Nav(s=S_SCHEDULES, c=ch.id).pack()), (t(lang, "btn_exemptions"), Nav(s=S_EXEMPT, c=ch.id).pack())])
    rows.append([(t(lang, "btn_history"), Nav(s=S_HISTORY, c=ch.id).pack())])
    rows.append(nav(lang, back=Nav(s=S_DASH, c=ch.id).pack(), refresh=Nav(s=S_SHIELD, c=ch.id).pack()))
    return text, kb(rows)


async def start_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str):
    shieldable = await admin_repo.list_shieldable(s, ch.id)
    counts = await admin_repo.count_by_status(s, ch.id)
    active = await admin_repo.list_for_channel(s, ch.id, statuses=("active",))
    exempt = sum(1 for a in active if a.shield_exempt)
    body = t(lang, "sst_hint", n=len(shieldable), exempt=exempt, unmanaged=counts.get("unmanaged", 0)) if shieldable else t(lang, "sst_none")
    text = compose(t(lang, "sst_title"), body)
    rows: list[list[tuple[str, str]]] = []
    if shieldable:
        rows.append([(t(lang, "dur_1h"), Act(a=A_SHIELD_START, c=ch.id, t="60").pack()), (t(lang, "dur_3h"), Act(a=A_SHIELD_START, c=ch.id, t="180").pack()), (t(lang, "dur_8h"), Act(a=A_SHIELD_START, c=ch.id, t="480").pack())])
        rows.append([(t(lang, "dur_manual"), Act(a=A_SHIELD_START, c=ch.id, t="manual").pack()), (t(lang, "dur_custom"), Act(a=A_SHIELD_START, c=ch.id, t="custom").pack())])
    rows.append(nav(lang, back=Nav(s=S_SHIELD, c=ch.id).pack()))
    return text, kb(rows)


async def schedules_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str):
    scheds = await repo.list_schedules(s, ch.id)
    labels = _day_labels(lang)
    if not scheds:
        text = compose(t(lang, "sch_title"), t(lang, "sch_empty"), footer=t(lang, "tz_line", tz=ch.timezone))
    else:
        rows_txt = [t(lang, "sch_row", glyph=G.ACTIVE if x.enabled else G.OFF, days=describe_days(x.weekdays if x.kind == "weekly" else ALL_DAYS, labels), start=x.start_time, end=x.end_time) for x in scheds]
        text = compose(t(lang, "sch_title"), (None, rows_txt), footer=t(lang, "tz_line", tz=ch.timezone))
    rows = [[(f"{G.ACTIVE if x.enabled else G.OFF} {x.start_time} → {x.end_time} · {t(lang, 'sch_daily') if x.kind == 'daily' else t(lang, 'sch_weekly')}", Nav(s=S_SCHEDULE, c=ch.id, a=str(x.id)).pack())] for x in scheds[:8]]
    rows.append([(t(lang, "btn_add_daily"), Act(a=A_SCHEDULE_ADD, c=ch.id, t="daily").pack()), (t(lang, "btn_add_weekly"), Act(a=A_SCHEDULE_ADD, c=ch.id, t="weekly").pack())])
    rows.append(nav(lang, back=Nav(s=S_SHIELD, c=ch.id).pack()))
    return text, kb(rows)


async def schedule_screen(ctx: Services, s: AsyncSession, ch: Channel, sched, lang: str):  # noqa: ANN001
    labels = _day_labels(lang)
    kind = t(lang, "sch_daily") if sched.kind == "daily" else t(lang, "sch_weekly")
    lines = [
        f"{G.ACTIVE if sched.enabled else G.OFF} {t(lang, 'sch_enabled') if sched.enabled else t(lang, 'sch_disabled')}",
        f"{kind} · {sched.start_time} → {sched.end_time}",
    ]
    if sched.kind == "weekly":
        lines.append(describe_days(sched.weekdays, labels))
    text = compose(t(lang, "sch_detail_title"), (None, lines), footer=t(lang, "sch_days_hint") if sched.kind == "weekly" else t(lang, "tz_line", tz=sched.timezone))
    rows: list[list[tuple[str, str]]] = []
    if sched.kind == "weekly":
        rows.append([(f"{G.ACTIVE if sched.weekdays & (1 << i) else G.OFF} {labels[i][:3]}", Act(a=A_SCHEDULE_DAY, c=ch.id, t=str(sched.id), v=str(i)).pack()) for i in range(7)])
    rows.append([(t(lang, "btn_disable" if sched.enabled else "btn_enable"), Act(a=A_SCHEDULE_TOGGLE, c=ch.id, t=str(sched.id)).pack()), (t(lang, "btn_delete_schedule"), Act(a=A_SCHEDULE_DEL, c=ch.id, t=str(sched.id)).pack())])
    rows.append(nav(lang, back=Nav(s=S_SCHEDULES, c=ch.id).pack()))
    return text, kb(rows)


async def exempt_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str):
    admins = [a for a in await admin_repo.list_for_channel(s, ch.id, statuses=("active", "shielded")) if a.managed_by_bot]
    text = compose(t(lang, "exm_title"), t(lang, "exm_hint") if admins else t(lang, "exm_empty"))
    rows = [[(f"{G.WAITING if a.shield_exempt else G.ACTIVE} {esc(a.display)[:30]}", Act(a=A_EXEMPT_TOGGLE, c=ch.id, t=str(a.id)).pack())] for a in admins[:20]]
    rows.append(nav(lang, back=Nav(s=S_SHIELD, c=ch.id).pack()))
    return text, kb(rows)


async def history_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str):
    sessions = await repo.list_recent_sessions(s, ch.id, limit=8)
    if not sessions:
        text = compose(t(lang, "hist_title"), t(lang, "hist_empty"))
    else:
        glyph = {"active": G.SHIELDED, "ending": G.SHIELDED, "ended": G.ACTIVE, "failed": G.ATTENTION}
        lines = [t(lang, "hist_row", glyph=glyph.get(x.status, G.WAITING), start=fmt_datetime(x.started_at, ch.timezone), end=fmt_clock(x.ended_at or x.ends_at, ch.timezone) if (x.ended_at or x.ends_at) else "…", trigger=t(lang, "trig_" + x.trigger)) for x in sessions]
        text = compose(t(lang, "hist_title"), (None, lines))
    return text, kb([nav(lang, back=Nav(s=S_SHIELD, c=ch.id).pack())])


SCREENS = {S_SHIELD: shield_screen, S_SHIELD_START: start_screen, S_SCHEDULES: schedules_screen, S_EXEMPT: exempt_screen, S_HISTORY: history_screen}


@router.callback_query(Nav.filter(F.s.in_(set(SCREENS))))
async def nav_shield(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    text, markup = await SCREENS[callback_data.s](ctx, s, ch, lang)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Nav.filter(F.s == S_SCHEDULE))
async def nav_schedule(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    sched = await repo.get_schedule(s, int(callback_data.a)) if callback_data.a.isdigit() else None
    if sched is None or sched.channel_id != ch.id:
        await toast(cb, t(lang, "toast_nothing"))
        return
    text, markup = await schedule_screen(ctx, s, ch, sched, lang)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Act.filter(F.a == A_SHIELD_START))
async def act_start(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    if callback_data.t == "custom":
        await state.set_state(Input.duration)
        await state.update_data(c=ch.id)
        await cb.message.answer(t(lang, "sst_custom_prompt"), reply_markup=cancel_kb(lang))
        await cb.answer()
        return
    ends_at = None if callback_data.t == "manual" else utcnow() + timedelta(minutes=int(callback_data.t))
    await show(cb, t(lang, "working"))
    msg = await _start(ctx, s, ch, user, lang, ends_at)
    text, markup = await shield_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, msg, alert=True)


async def _start(ctx: Services, s: AsyncSession, ch: Channel, user: User, lang: str, ends_at) -> str:  # noqa: ANN001
    try:
        outcome = await ctx.shield.start(s, ch, by=user.id, trigger="manual", ends_at=ends_at)
    except BotRightsMissing as e:
        return t(lang, "err_bot_rights", rights=right_labels(lang, e.missing))
    if outcome is None:
        return t(lang, "sst_already")
    return t(lang, "sst_done", n=len(outcome.suspended), skipped=len(outcome.skipped))


@router.message(Input.duration, F.chat.type == "private")
async def input_duration(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(message, ctx, s, user, int(data.get("c", 0)), lang)
    if ch is None:
        await state.clear()
        return
    delta = parse_duration(message.text or "")
    if delta is None or delta > timedelta(days=30):
        await message.answer(t(lang, "sst_invalid"))
        return
    await state.clear()
    msg = await _start(ctx, s, ch, user, lang, utcnow() + delta)
    text, markup = await shield_screen(ctx, s, ch, lang)
    await message.answer(msg)
    await message.answer(text, reply_markup=markup)


@router.callback_query(Act.filter(F.a == A_SHIELD_STOP))
async def act_stop(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    sess = await repo.active_session(s, ch.id)
    if sess is None:
        text, markup = await shield_screen(ctx, s, ch, lang)
        await show(cb, text, markup)
        await toast(cb, t(lang, "toast_nothing"))
        return
    if callback_data.v != "ok":
        members = await repo.list_unrestored_members(s, sess.id)
        text = compose(t(lang, "shd_title"), t(lang, "ssp_confirm", n=len(members)))
        markup = kb([[(t(lang, "confirm"), Act(a=A_SHIELD_STOP, c=ch.id, v="ok").pack())], [(t(lang, "cancel"), Nav(s=S_SHIELD, c=ch.id).pack())]])
        await show(cb, text, markup)
        await cb.answer()
        return
    await show(cb, t(lang, "working"))
    outcome = await ctx.shield.end(s, sess, by=user.id, reason="manual")
    msg = t(lang, "ssp_done", restored=len(outcome.restored), failed=len(outcome.failed))
    text, markup = await shield_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, msg, alert=True)


@router.callback_query(Act.filter(F.a == A_RETRY_SHIELD))
async def act_retry(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    sess = await repo.get_session(s, int(callback_data.t)) if callback_data.t.isdigit() else None
    if sess is None or sess.channel_id != ch.id:
        await toast(cb, t(lang, "toast_nothing"))
        return
    outcome = await ctx.shield.retry_session(s, sess, by=user.id)
    await toast(cb, t(lang, "ssp_done", restored=len(outcome.restored), failed=len(outcome.failed)), alert=True)
    text, markup = await shield_screen(ctx, s, ch, lang)
    await show(cb, text, markup, new=True)


@router.callback_query(Act.filter(F.a == A_SCHEDULE_ADD))
async def act_schedule_add(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    await state.set_state(Input.sched_start)
    await state.update_data(c=ch.id, kind="weekly" if callback_data.t == "weekly" else "daily")
    await cb.message.answer(t(lang, "sch_start_prompt"), reply_markup=cancel_kb(lang))
    await cb.answer()


@router.message(Input.sched_start, F.chat.type == "private")
async def input_sched_start(message: Message, lang: str, state: FSMContext) -> None:
    tm = parse_hhmm(message.text or "")
    if tm is None:
        await message.answer(t(lang, "sch_invalid_time"))
        return
    await state.update_data(start=tm.strftime("%H:%M"))
    await state.set_state(Input.sched_end)
    await message.answer(t(lang, "sch_end_prompt"), reply_markup=cancel_kb(lang))


@router.message(Input.sched_end, F.chat.type == "private")
async def input_sched_end(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    data = await state.get_data()
    ch = await guard_channel(message, ctx, s, user, int(data.get("c", 0)), lang)
    if ch is None:
        await state.clear()
        return
    tm = parse_hhmm(message.text or "")
    if tm is None:
        await message.answer(t(lang, "sch_invalid_time"))
        return
    sched = await repo.create_schedule(s, channel_id=ch.id, kind=data.get("kind", "daily"), start_time=data["start"], end_time=tm.strftime("%H:%M"), weekdays=ALL_DAYS, timezone=ch.timezone, enabled=True, created_by=user.id)
    await audit.log(s, "shield.schedule_added", channel_id=ch.id, actor=user.id, target_type="schedule", target_id=sched.id, kind=sched.kind, start=sched.start_time, end=sched.end_time)
    await state.clear()
    text, markup = await schedule_screen(ctx, s, ch, sched, lang)
    await message.answer(t(lang, "sch_saved"))
    await message.answer(text, reply_markup=markup)


@router.callback_query(Act.filter(F.a.in_({A_SCHEDULE_DAY, A_SCHEDULE_TOGGLE, A_SCHEDULE_DEL})))
async def act_schedule_edit(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    sched = await repo.get_schedule(s, int(callback_data.t)) if callback_data.t.isdigit() else None
    if sched is None or sched.channel_id != ch.id:
        await toast(cb, t(lang, "toast_nothing"))
        return
    if callback_data.a == A_SCHEDULE_DEL:
        await repo.delete_schedule(s, sched)
        await audit.log(s, "shield.schedule_deleted", channel_id=ch.id, actor=user.id, target_type="schedule", target_id=callback_data.t)
        text, markup = await schedules_screen(ctx, s, ch, lang)
        await show(cb, text, markup)
        await toast(cb, t(lang, "sch_deleted"))
        return
    if callback_data.a == A_SCHEDULE_TOGGLE:
        sched.enabled = not sched.enabled
        await audit.log(s, "shield.schedule_toggled", channel_id=ch.id, actor=user.id, target_type="schedule", target_id=sched.id, enabled=sched.enabled)
    else:
        idx = int(callback_data.v) if callback_data.v.isdigit() else 0
        sched.weekdays = int(sched.weekdays or 0) ^ (1 << idx)
        if sched.weekdays == 0:
            sched.weekdays = 1 << idx
    await s.flush()
    text, markup = await schedule_screen(ctx, s, ch, sched, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "toast_saved"))


@router.callback_query(Act.filter(F.a == A_EXEMPT_TOGGLE))
async def act_exempt_toggle(cb: CallbackQuery, callback_data: Act, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    a = await admin_repo.get(s, int(callback_data.t)) if callback_data.t.isdigit() else None
    if a is None or a.channel_id != ch.id:
        await toast(cb, t(lang, "toast_nothing"))
        return
    await ctx.admins.set_exempt(s, ch, a, not a.shield_exempt, by=user.id)
    text, markup = await exempt_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "exempt_on_ok" if a.shield_exempt else "exempt_off_ok"))
