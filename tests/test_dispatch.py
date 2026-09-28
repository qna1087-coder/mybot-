"""Wiring test: real aiogram Dispatcher + middlewares + handlers, with a mocked Telegram session."""

from __future__ import annotations

import time
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.types import Message, Update, User

from vigil.app import build_dispatcher, build_services
from vigil.config import Settings
from vigil.db.engine import Database
from vigil.telegram.callbacks import Nav

from .conftest import BOT_ID, CHANNEL_ID, FakeBot


class MockedSession(BaseSession):
    def __init__(self, fake: FakeBot):
        super().__init__()
        self.fake = fake
        self.calls: list[Any] = []

    async def close(self) -> None:  # noqa: D401
        pass

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover
        raise NotImplementedError

    async def make_request(self, bot: Bot, method: Any, timeout: int | None = None) -> Any:
        self.calls.append(method)
        name = type(method).__name__
        if name == "GetMe":
            return User(id=BOT_ID, is_bot=True, first_name="Vigil", username="vigil_bot")
        if name in ("SendMessage", "EditMessageText"):
            chat_id = method.chat_id
            return Message.model_validate({"message_id": 500 + len(self.calls), "date": int(time.time()), "chat": {"id": chat_id, "type": "private", "first_name": "x"}, "text": method.text})
        if name in ("AnswerCallbackQuery", "SetMyCommands", "DeleteWebhook", "DeleteMessage", "DeleteMessages"):
            if name == "DeleteMessage":
                self.fake.deleted.append((method.chat_id, [method.message_id]))
            return True
        if name == "GetChatAdministrators":
            return await self.fake.get_chat_administrators(method.chat_id)
        if name == "GetChatMember":
            return await self.fake.get_chat_member(method.chat_id, method.user_id)
        if name == "PromoteChatMember":
            data = method.model_dump(exclude={"chat_id", "user_id"}, exclude_none=True)
            return await self.fake.promote_chat_member(method.chat_id, method.user_id, **data)
        raise NotImplementedError(name)

    def sent_texts(self) -> list[str]:
        return [m.text for m in self.calls if type(m).__name__ in ("SendMessage", "EditMessageText")]


def private_message(uid: int, text: str, lang: str = "ar") -> Update:
    ents = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}] if text.startswith("/") else []
    return Update(update_id=int(time.time() * 1000) % 10**9, message=Message.model_validate({
        "message_id": 1, "date": int(time.time()),
        "chat": {"id": uid, "type": "private", "first_name": "Owner"},
        "from": {"id": uid, "is_bot": False, "first_name": "Owner", "language_code": lang},
        "text": text, "entities": ents,
    }))


def callback(uid: int, data: str) -> Update:
    return Update(update_id=2, callback_query={
        "id": "cb1", "chat_instance": "ci",
        "from": {"id": uid, "is_bot": False, "first_name": "Owner"},
        "data": data,
        "message": {"message_id": 10, "date": int(time.time()), "chat": {"id": uid, "type": "private", "first_name": "Owner"}, "text": "old"},
    })


def bot_added(actor_id: int) -> Update:
    admin = {"status": "administrator", "user": {"id": BOT_ID, "is_bot": True, "first_name": "Vigil", "username": "vigil_bot"}, "can_be_edited": False, "is_anonymous": False,
             "can_manage_chat": True, "can_delete_messages": True, "can_manage_video_chats": False, "can_restrict_members": False, "can_promote_members": True,
             "can_change_info": False, "can_invite_users": False, "can_post_stories": False, "can_edit_stories": False, "can_delete_stories": False,
             "can_send_welcome_messages": False, "can_post_messages": True, "can_edit_messages": False, "can_pin_messages": False}
    return Update(update_id=3, my_chat_member={
        "chat": {"id": CHANNEL_ID, "type": "channel", "title": "Test Channel"},
        "from": {"id": actor_id, "is_bot": False, "first_name": "Owner"},
        "date": int(time.time()),
        "old_chat_member": {"status": "left", "user": admin["user"]},
        "new_chat_member": admin,
    })


def _detach_routers() -> None:
    from vigil.telegram.handlers.channel import membership, posts
    from vigil.telegram.handlers.private import (
        activity,
        admins,
        channels,
        emoji,
        guard,
        shield,
        start,
        system,
    )
    from vigil.telegram.handlers.private import settings as settings_h

    for mod in (start, channels, admins, guard, emoji, shield, activity, settings_h, system, posts, membership):
        mod.router._parent_router = None  # test-only reset


@pytest.fixture
async def stack(tmp_path):
    cfg = Settings(bot_token="123456:TEST-TOKEN-NOT-REAL-XXXXXXXXXXXXXXXX", system_owner_id=100, openrouter_api_key="", database_url=f"sqlite+aiosqlite:///{tmp_path}/d.db", default_timezone="UTC")
    db = Database(cfg.database_url)
    await db.init()
    fake = FakeBot()
    session = MockedSession(fake)
    bot = Bot(cfg.bot_token, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    ctx = build_services(cfg, db, bot)
    ctx.bot_user = await bot.get_me()
    _detach_routers()  # module-level routers can only be attached to one Dispatcher
    dp = build_dispatcher(ctx)
    yield dp, bot, session, ctx
    await ctx.moderation.close()
    await db.dispose()


async def test_start_and_system_panel(stack):
    dp, bot, session, ctx = stack
    res = await dp.feed_update(bot, private_message(100, "/start"))
    assert res is not UNHANDLED
    texts = session.sent_texts()
    assert texts and "Vigil" in texts[-1] and "@vigil_bot" in texts[-1]
    # Arabic client → Arabic microcopy
    assert "حماية" in texts[-1]

    await dp.feed_update(bot, callback(100, Nav(s="sys").pack()))
    texts = session.sent_texts()
    assert "النظام" in texts[-1]
    assert any(type(m).__name__ == "AnswerCallbackQuery" for m in session.calls)


async def test_non_owner_is_denied_system_panel(stack):
    dp, bot, session, ctx = stack
    await dp.feed_update(bot, private_message(555, "/start", lang="en"))
    before = len(session.sent_texts())
    await dp.feed_update(bot, callback(555, Nav(s="sys").pack()))
    assert len(session.sent_texts()) == before  # nothing rendered
    answers = [m for m in session.calls if type(m).__name__ == "AnswerCallbackQuery"]
    assert answers and "permitted" in (answers[-1].text or "").lower()


async def test_bot_added_to_channel_creates_pending_and_notifies_owner(stack):
    dp, bot, session, ctx = stack
    await dp.feed_update(bot, private_message(100, "/start"))
    await dp.feed_update(bot, bot_added(actor_id=1))
    from vigil.db.repo import channels as ch_repo

    async with ctx.db.session() as s:
        ch = await ch_repo.get(s, CHANNEL_ID)
        assert ch is not None and ch.status == "pending" and ch.added_by == 1
    sent = [m for m in session.calls if type(m).__name__ == "SendMessage"]
    # system owner (100) got the activation card with an Activate button
    card = [m for m in sent if m.chat_id == 100 and m.reply_markup is not None]
    assert card, "system owner should receive the pending card"
    buttons = [b.callback_data for row in card[-1].reply_markup.inline_keyboard for b in row]
    assert any(d and d.startswith("x:cha:") for d in buttons)
