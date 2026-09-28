"""One door for every Telegram call.

Rate limits are respected exactly (RetryAfter), transient network/server errors are retried
with backoff, and permanent errors are classified so callers can react calmly.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
)

log = logging.getLogger("vigil.tg")
T = TypeVar("T")


async def tg(call: Callable[[], Awaitable[T]], *, retries: int = 4, label: str = "") -> T:
    """Execute a Telegram call with RetryAfter/backoff handling."""
    attempt = 0
    delay = 1.0
    while True:
        try:
            return await call()
        except TelegramRetryAfter as e:
            attempt += 1
            wait = min(float(e.retry_after) + 0.5, 90.0)
            log.warning("flood wait %.1fs (%s)", wait, label)
            if attempt > retries:
                raise
            await asyncio.sleep(wait)
        except (TelegramNetworkError, TelegramServerError) as e:
            attempt += 1
            if attempt > retries:
                raise
            log.warning("transient telegram error (%s): %s — retry %d in %.1fs", label, e, attempt, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 16.0)


def is_not_modified(exc: BaseException) -> bool:
    return isinstance(exc, TelegramBadRequest) and "message is not modified" in str(exc).lower()


def is_message_gone(exc: BaseException) -> bool:
    if isinstance(exc, TelegramNotFound):
        return True
    s = str(exc).lower()
    return isinstance(exc, TelegramBadRequest) and (
        "message to delete not found" in s
        or "message to edit not found" in s
        or "message can't be deleted" in s
        or "message_id_invalid" in s
    )


def is_forbidden(exc: BaseException) -> bool:
    return isinstance(exc, TelegramForbiddenError)


def is_rights_error(exc: BaseException) -> bool:
    """The bot lacks the right, or Telegram's promote-ownership rule blocks the demotion."""
    s = str(exc).lower()
    return isinstance(exc, TelegramAPIError) and (
        "chat_admin_required" in s
        or "not enough rights" in s
        or "can't remove chat owner" in s
        or "user is an administrator of the chat" in s
        or "right_forbidden" in s
        or "admin_rank_emoji_not_allowed" in s
        or "chat_admin_invite_required" in s
        or "user_not_mutual_contact" in s
        or "method is available only for supergroups" in s
    )


def short_error(exc: BaseException) -> str:
    text = str(exc)
    for prefix in ("Telegram server says - ", "Bad Request: ", "Forbidden: "):
        text = text.replace(prefix, "")
    return text.strip()[:200]
