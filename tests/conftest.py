from __future__ import annotations

import os
import time
from typing import Any

import pytest
from aiogram.types import (
    Chat,
    ChatMemberAdministrator,
    ChatMemberLeft,
    ChatMemberOwner,
    Message,
    Sticker,
    StickerSet,
    User,
)

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN-NOT-REAL-XXXXXXXXXXXXXXXX")
os.environ.setdefault("SYSTEM_OWNER_ID", "100")
os.environ.setdefault("OPENROUTER_API_KEY", "")

from vigil.config import Settings  # noqa: E402
from vigil.db.engine import Database  # noqa: E402

CHANNEL_ID = -1001234567890
BOT_ID = 999


def tg_user(uid: int, first: str, last: str = "", username: str | None = None, is_bot: bool = False) -> User:
    return User(id=uid, is_bot=is_bot, first_name=first, last_name=last or None, username=username)


def admin_member(uid: int, first: str, *, can_be_edited: bool, custom_title: str | None = None, is_bot: bool = False, **rights: bool) -> ChatMemberAdministrator:
    base = dict(
        can_manage_chat=True, can_delete_messages=True, can_manage_video_chats=False, can_restrict_members=False,
        can_promote_members=False, can_change_info=False, can_invite_users=False, can_post_stories=False,
        can_edit_stories=False, can_delete_stories=False, can_send_welcome_messages=False,
        can_post_messages=True, can_edit_messages=True, can_pin_messages=False,
    )
    base.update(rights)
    return ChatMemberAdministrator(user=tg_user(uid, first, is_bot=is_bot), can_be_edited=can_be_edited, is_anonymous=False, custom_title=custom_title, **base)


class FakeBot:
    """Records every Telegram call. Behaves like a channel where the bot promoted admin 2 only."""

    def __init__(self):
        self.id = BOT_ID
        self.admins: dict[int, Any] = {
            1: ChatMemberOwner(user=tg_user(1, "Owner"), is_anonymous=False),
            2: admin_member(2, "Ahmed", can_be_edited=True),
            3: admin_member(3, "Sara", can_be_edited=False, custom_title="Editor"),
            BOT_ID: admin_member(BOT_ID, "Vigil", can_be_edited=False, is_bot=True, can_promote_members=True, can_delete_messages=True, can_post_messages=True),
        }
        self.promotions: list[tuple[int, int, dict[str, bool]]] = []
        self.deleted: list[tuple[int, list[int]]] = []
        self.sent: list[tuple[int, str]] = []
        self.fail_promote_for: set[int] = set()

    async def get_chat_administrators(self, chat_id: int):
        return list(self.admins.values())

    async def get_chat_member(self, chat_id: int, user_id: int):
        m = self.admins.get(user_id)
        if m is None:
            return ChatMemberLeft(user=tg_user(user_id, f"U{user_id}"))
        return m

    async def promote_chat_member(self, chat_id: int, user_id: int, **rights: bool):
        from aiogram.exceptions import TelegramBadRequest
        from aiogram.methods import PromoteChatMember

        if user_id in self.fail_promote_for:
            raise TelegramBadRequest(PromoteChatMember(chat_id=chat_id, user_id=user_id), "Bad Request: CHAT_ADMIN_REQUIRED")
        self.promotions.append((chat_id, user_id, dict(rights)))
        current = self.admins.get(user_id)
        if not any(v for k, v in rights.items() if k != "is_anonymous"):
            if isinstance(current, ChatMemberAdministrator):
                self.admins.pop(user_id, None)
        else:
            name = current.user.first_name if current is not None else f"U{user_id}"
            self.admins[user_id] = admin_member(user_id, name, can_be_edited=True, **{k: v for k, v in rights.items() if k != "is_anonymous"})
        return True

    async def delete_message(self, chat_id: int, message_id: int):
        self.deleted.append((chat_id, [message_id]))
        return True

    async def delete_messages(self, chat_id: int, message_ids: list[int]):
        self.deleted.append((chat_id, list(message_ids)))
        return True

    async def send_message(self, chat_id: int, text: str, **kwargs: Any):
        self.sent.append((chat_id, text))
        return Message.model_validate({"message_id": len(self.sent), "date": int(time.time()), "chat": {"id": chat_id, "type": "private", "first_name": "x"}, "text": text})

    async def get_sticker_set(self, name: str):
        if name != "VigilPack":
            from aiogram.exceptions import TelegramBadRequest
            from aiogram.methods import GetStickerSet

            raise TelegramBadRequest(GetStickerSet(name=name), "Bad Request: STICKERSET_INVALID")
        stickers = [
            Sticker(file_id=f"f{i}", file_unique_id=f"u{i}", type="custom_emoji", width=100, height=100, is_animated=False, is_video=False, emoji="✦", set_name="VigilPack", custom_emoji_id=str(5000000000000000000 + i))
            for i in range(3)
        ]
        return StickerSet(name="VigilPack", title="Vigil Pack", sticker_type="custom_emoji", stickers=stickers)

    async def get_custom_emoji_stickers(self, custom_emoji_ids: list[str]):
        return [
            Sticker(file_id="f", file_unique_id="u", type="custom_emoji", width=1, height=1, is_animated=False, is_video=False, emoji="✦", set_name="VigilPack", custom_emoji_id=cid)
            for cid in custom_emoji_ids
            if cid.startswith("5000000000000000")
        ]


def make_post(message_id: int, *, text: str | None = None, caption: str | None = None, entities: list[dict] | None = None, author_signature: str | None = "Ahmed", **extra: Any) -> Message:
    d: dict[str, Any] = {
        "message_id": message_id,
        "date": int(time.time()),
        "chat": {"id": CHANNEL_ID, "type": "channel", "title": "Test Channel"},
        "sender_chat": {"id": CHANNEL_ID, "type": "channel", "title": "Test Channel"},
    }
    if author_signature:
        d["author_signature"] = author_signature
    if text is not None:
        d["text"] = text
    if caption is not None:
        d["caption"] = caption
    if entities:
        d["entities" if text is not None else "caption_entities"] = entities
    d.update(extra)
    return Message.model_validate(d)


def photo() -> list[dict]:
    return [{"file_id": "p", "file_unique_id": "pu", "width": 10, "height": 10}]


@pytest.fixture
def channel_chat() -> Chat:
    return Chat(id=CHANNEL_ID, type="channel", title="Test Channel")


@pytest.fixture
async def ctx(tmp_path):
    from vigil.app import build_services

    cfg = Settings(bot_token="123456:TEST-TOKEN-NOT-REAL-XXXXXXXXXXXXXXXX", system_owner_id=100, openrouter_api_key="", database_url=f"sqlite+aiosqlite:///{tmp_path}/t.db", default_timezone="UTC")
    db = Database(cfg.database_url)
    await db.init()
    bot = FakeBot()
    services = build_services(cfg, db, bot)  # type: ignore[arg-type]
    services.bot_user = tg_user(BOT_ID, "Vigil", is_bot=True, username="vigil_bot")
    yield services
    await services.moderation.close()
    await db.dispose()
