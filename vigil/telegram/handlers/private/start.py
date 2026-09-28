from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.models import User
from vigil.services.context import Services
from vigil.telegram.callbacks import A_CANCEL, A_NOOP, S_HELP, S_HOME, Act, Nav
from vigil.telegram.handlers.private.common import home
from vigil.telegram.ui.screens import compose, kb, nav, show, toast
from vigil.telegram.ui.texts import t

router = Router(name="private_start")
router.message.filter(F.chat.type == "private")


@router.message(CommandStart())
async def cmd_start(message: Message, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    await state.clear()
    text, markup = await home(ctx, s, user, lang)
    await message.answer(text, reply_markup=markup)


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str) -> None:
    await message.answer(compose(t(lang, "help_title"), t(lang, "help_body")), reply_markup=kb([nav(lang, home=True)]))


@router.message(Command("id"))
async def cmd_id(message: Message, lang: str) -> None:
    await message.answer(t(lang, "your_id", id=message.from_user.id if message.from_user else 0))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, lang: str, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t(lang, "input_cancelled"), reply_markup=ReplyKeyboardRemove())


@router.callback_query(Nav.filter(F.s == S_HOME))
async def nav_home(cb: CallbackQuery, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    await state.clear()
    text, markup = await home(ctx, s, user, lang)
    await show(cb, text, markup)
    await cb.answer()


@router.callback_query(Nav.filter(F.s == S_HELP))
async def nav_help(cb: CallbackQuery, lang: str) -> None:
    await show(cb, compose(t(lang, "help_title"), t(lang, "help_body")), kb([nav(lang, home=True)]))
    await cb.answer()


@router.callback_query(Act.filter(F.a == A_CANCEL))
async def act_cancel(cb: CallbackQuery, ctx: Services, s: AsyncSession, user: User, lang: str, state: FSMContext) -> None:
    await state.clear()
    text, markup = await home(ctx, s, user, lang)
    await show(cb, text, markup)
    await toast(cb, t(lang, "toast_cancelled"))


@router.callback_query(Act.filter(F.a == A_NOOP))
async def act_noop(cb: CallbackQuery) -> None:
    await cb.answer()
