"""Per-update database session, user context, and calm error handling."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from vigil.db.repo import users as user_repo
from vigil.services.context import Services

log = logging.getLogger("vigil.mw")


class DbMiddleware(BaseMiddleware):
    def __init__(self, ctx: Services):
        self.ctx = ctx

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.ctx.db.session() as s:
            data["s"] = s
            data["ctx"] = self.ctx
            return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    """Upserts the user record for private interactions and exposes `user` and `lang`."""

    def __init__(self, ctx: Services):
        self.ctx = ctx

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Update):
            inner = event.message or event.callback_query or event.edited_message
        else:
            inner = event
        if isinstance(inner, Message | CallbackQuery):
            tg_user = inner.from_user
        s = data.get("s")
        if tg_user is not None and s is not None and not tg_user.is_bot:
            chat_type = None
            if isinstance(inner, Message):
                chat_type = inner.chat.type
            elif isinstance(inner, CallbackQuery) and inner.message is not None:
                chat_type = inner.message.chat.type
            if chat_type == "private":
                user = await user_repo.upsert_from_tg(s, tg_user, default_lang=self.ctx.config.default_language)
                if not user.dm_ok:
                    user.dm_ok = True
                if self.ctx.access.is_system_owner(user.id) and user.role != "owner":
                    user.role = "owner"
                data["user"] = user
                data["lang"] = user.lang
        data.setdefault("lang", self.ctx.config.default_language)
        return await handler(event, data)
