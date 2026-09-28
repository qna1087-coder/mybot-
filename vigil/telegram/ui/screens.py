"""Screen composition and keyboard helpers — the one place layout rules live."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from vigil.core import glyphs as G
from vigil.core.retry import is_message_gone, is_not_modified, tg
from vigil.telegram.callbacks import Nav
from vigil.telegram.ui.texts import t

log = logging.getLogger("vigil.ui")

Button = tuple[str, str]  # (label, callback_data)


def compose(title: str, *sections: Any, footer: str | None = None, rule: bool = True) -> str:
    """title + divider, then sections. A section is a str, or (heading, [lines])."""
    parts: list[str] = [f"<b>{title}</b>"]
    if rule:
        parts.append(G.RULE)
    for sec in sections:
        if sec is None:
            continue
        parts.append("")
        if isinstance(sec, str):
            parts.append(sec)
        else:
            heading, lines = sec
            if heading:
                parts.append(f"<b>{heading}</b>")
            parts.extend(line for line in lines if line is not None)
    if footer:
        parts.append("")
        parts.append(f"<i>{footer}</i>")
    return "\n".join(parts)


def line(glyph: str, text: str, *extra: str) -> str:
    tail = f"  {G.DOT}  ".join(x for x in extra if x)
    return f"{glyph} {text}" + (f"  {G.DOT}  {tail}" if tail else "")


def kb(rows: Sequence[Sequence[Button]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=data) for label, data in row if label]
            for row in rows
            if row
        ]
    )


def kb_urls(rows: Sequence[Sequence[tuple[str, str, bool]]]) -> InlineKeyboardMarkup:
    """(label, data_or_url, is_url)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label, url=data) if is_url else InlineKeyboardButton(text=label, callback_data=data)
                for label, data, is_url in row
            ]
            for row in rows
            if row
        ]
    )


def nav(lang: str, *, back: str | None = None, refresh: str | None = None, home: bool = False) -> list[Button]:
    row: list[Button] = []
    if back:
        row.append((t(lang, "back"), back))
    if home:
        row.append((t(lang, "home"), Nav(s="home").pack()))
    if refresh:
        row.append((t(lang, "refresh"), refresh))
    return row


def pager(lang: str, *, screen: str, channel: int, arg: str, page: int, total_pages: int) -> list[Button]:
    row: list[Button] = []
    if page > 0:
        row.append((t(lang, "prev"), Nav(s=screen, c=channel, a=arg, p=page - 1).pack()))
    if total_pages > 1:
        row.append((t(lang, "page", cur=page + 1, total=total_pages), Nav(s=screen, c=channel, a=arg, p=page).pack()))
    if page + 1 < total_pages:
        row.append((t(lang, "next"), Nav(s=screen, c=channel, a=arg, p=page + 1).pack()))
    return row


async def show(event: Message | CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None, *, new: bool = False) -> Message | None:
    """Edit in place for callbacks; send for messages. Silences 'not modified'."""
    if isinstance(event, CallbackQuery):
        msg = event.message
        if msg is not None and not new and isinstance(msg, Message):
            try:
                return await tg(lambda: msg.edit_text(text, reply_markup=markup), label="editMessageText")
            except TelegramBadRequest as e:
                if is_not_modified(e):
                    return msg
                if not is_message_gone(e) and "there is no text in the message" not in str(e).lower():
                    log.debug("edit failed, sending new: %s", e)
        chat_id = msg.chat.id if msg is not None else event.from_user.id
        return await tg(lambda: event.bot.send_message(chat_id, text, reply_markup=markup), label="sendMessage")
    return await tg(lambda: event.answer(text, reply_markup=markup), label="sendMessage")


async def toast(cb: CallbackQuery, text: str, *, alert: bool = False) -> None:
    try:
        await cb.answer(text[:200], show_alert=alert)
    except TelegramAPIError:
        pass


def paginate(items: list[Any], page: int, per_page: int) -> tuple[list[Any], int, int]:
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    return items[page * per_page : (page + 1) * per_page], page, total_pages


def onoff(lang: str, value: bool) -> str:
    return f"{G.ACTIVE} {t(lang, 'on')}" if value else f"{G.OFF} {t(lang, 'off')}"


def toggle_label(lang: str, label: str, value: bool) -> str:
    return f"{G.ACTIVE if value else G.OFF} {label}"
