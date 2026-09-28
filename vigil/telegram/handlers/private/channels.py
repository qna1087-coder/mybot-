from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.models import User
from vigil.db.repo import channels as ch_repo
from vigil.services.context import Services
from vigil.telegram.callbacks import S_BOT_RIGHTS, S_CHANNELS, S_DASH, Nav
from vigil.telegram.handlers.private.common import (
    bot_rights_screen,
    channel_state,
    dashboard,
    guard_channel,
)
from vigil.telegram.ui.screens import compose, kb, nav, pager, paginate, show
from vigil.telegram.ui.texts import esc, t

router = Router(name="private_channels")


@router.callback_query(Nav.filter(F.s == S_CHANNELS))
async def nav_channels(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    is_system = await ctx.access.is_system_admin(s, user.id)
    channels = await ch_repo.list_all(s) if is_system else await ch_repo.list_for_user(s, user.id)
    if not channels:
        await show(cb, compose(t(lang, "chs_title"), t(lang, "chs_empty")), kb([nav(lang, home=True)]))
        await cb.answer()
        return
    items, page, total = paginate(channels, callback_data.p, 8)
    rows = [[(f"{channel_state(lang, c)[0]} {esc(c.title)[:40]}", Nav(s=S_DASH, c=c.id).pack())] for c in items]
    rows.append(pager(lang, screen=S_CHANNELS, channel=0, arg="", page=page, total_pages=total))
    rows.append(nav(lang, home=True))
    text = compose(t(lang, "chs_title"), *[f"{channel_state(lang, c)} · {esc(c.title)}" for c in items])
    await show(cb, text, kb(rows))
    await cb.answer()


@router.callback_query(Nav.filter(F.s == S_DASH))
async def nav_dashboard(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    is_system = await ctx.access.is_system_admin(s, user.id)
    text, markup = await dashboard(ctx, s, ch, lang, is_system=is_system)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Nav.filter(F.s == S_BOT_RIGHTS))
async def nav_bot_rights(cb: CallbackQuery, callback_data: Nav, ctx: Services, s: AsyncSession, user: User, lang: str) -> None:
    ch = await guard_channel(cb, ctx, s, user, callback_data.c, lang)
    if ch is None:
        return
    text, markup = await bot_rights_screen(ctx, s, ch, lang)
    await show(cb, text, markup)
    await cb.answer()
