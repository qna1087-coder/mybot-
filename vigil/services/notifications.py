"""Delivery of cards to the right people in their own language, with rate limits and DM fallbacks."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.retry import short_error, tg
from vigil.core.timeutil import utcnow
from vigil.db.models import Admin, Channel, ShieldMember, Violation
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import audit
from vigil.db.repo import permissions as perm_repo
from vigil.db.repo import users as user_repo
from vigil.services.context import Services
from vigil.telegram.ui import cards
from vigil.telegram.ui.texts import t

log = logging.getLogger("vigil.notify")

Render = Callable[[str], tuple[str, InlineKeyboardMarkup | None]]


class Notifier:
    def __init__(self, ctx: Services):
        self.ctx = ctx
        self._throttle: dict[str, float] = {}

    # ── primitives ───────────────────────────────────────────

    def _allow(self, key: str, seconds: float) -> bool:
        now = time.monotonic()
        last = self._throttle.get(key, 0.0)
        if now - last < seconds:
            return False
        self._throttle[key] = now
        return True

    async def send(self, s: AsyncSession, user_id: int, render: Render) -> Any | None:
        user = await user_repo.get(s, user_id)
        lang = user.lang if user else self.ctx.config.default_language
        text, markup = render(lang)
        try:
            msg = await tg(lambda: self.ctx.bot.send_message(user_id, text, reply_markup=markup), label="notify")
            if user is not None and not user.dm_ok:
                user.dm_ok = True
            return msg
        except TelegramForbiddenError:
            if user is not None:
                user.dm_ok = False
            return None
        except TelegramAPIError as e:
            log.warning("notify %s failed: %s", user_id, short_error(e))
            return None

    async def _recipients(self, s: AsyncSession, ch: Channel) -> list[int]:
        ids: list[int] = []
        for p in await perm_repo.list_for_channel(s, ch.id):
            user = await user_repo.get(s, p.user_id)
            if user is None or user.dm_ok:
                ids.append(p.user_id)
        if ch.owner_user_id and ch.owner_user_id not in ids:
            ids.append(ch.owner_user_id)
        return ids

    async def _system_recipients(self, s: AsyncSession) -> list[int]:
        ids = {self.ctx.config.system_owner_id}
        for u in await user_repo.list_by_role(s, "admin"):
            ids.add(u.id)
        return sorted(ids)

    async def to_managers(self, s: AsyncSession, ch: Channel, render: Render, *, include_system: bool = False) -> list[Any]:
        sent: list[Any] = []
        targets = await self._recipients(s, ch)
        if include_system:
            targets = list(dict.fromkeys(targets + await self._system_recipients(s)))
        for uid in targets:
            msg = await self.send(s, uid, render)
            if msg is not None:
                sent.append(msg)
        if not sent and not include_system:
            for uid in await self._system_recipients(s):
                msg = await self.send(s, uid, render)
                if msg is not None:
                    sent.append(msg)
        return sent

    async def to_system(self, s: AsyncSession, render: Render) -> list[Any]:
        sent = []
        for uid in await self._system_recipients(s):
            msg = await self.send(s, uid, render)
            if msg is not None:
                sent.append(msg)
        return sent

    # ── events ───────────────────────────────────────────────

    async def violation(
        self,
        s: AsyncSession,
        ch: Channel,
        v: Violation,
        admin: Admin | None,
        *,
        attribution: Any,
        demoted: bool,
        deleted: bool,
        could_not: str | None,
        notify_system: bool,
    ) -> None:
        def render(lang: str) -> tuple[str, InlineKeyboardMarkup | None]:
            return cards.violation_card(
                lang, ch, v, admin,
                attribution_status=attribution.status, signature=attribution.signature,
                demoted=demoted, deleted=deleted, could_not=could_not,
            )

        await self.to_managers(s, ch, render, include_system=notify_system)

    async def shield_started(self, s: AsyncSession, ch: Channel, outcome: Any) -> None:
        await self.to_managers(s, ch, lambda lang: cards.shield_on_card(lang, ch, outcome))

    async def shield_ended(self, s: AsyncSession, ch: Channel, outcome: Any) -> None:
        names: dict[int, str] = {}
        for m, _ in outcome.failed:
            a = await admin_repo.get_by_user(s, ch.id, m.user_id)
            names[m.user_id] = a.display if a else str(m.user_id)
        await self.to_managers(s, ch, lambda lang: cards.shield_off_card(lang, ch, outcome, names))

    async def shield_member_restored(self, s: AsyncSession, ch: Channel, member: ShieldMember) -> None:
        a = await admin_repo.get_by_user(s, ch.id, member.user_id)
        name = a.display if a else str(member.user_id)
        await self.to_managers(s, ch, lambda lang: (cards.member_restored_card(lang, ch, name), None))

    async def api_failure(self, s: AsyncSession, ch: Channel, error: str) -> None:
        await audit.log(s, "api.failure", channel_id=ch.id, error=error[:255])
        if not self._allow(f"api:{ch.id}", 3600):
            return
        settings = await self.ctx.settings.get(s, ch.id)
        mode = settings.api_fail_mode if settings.api_fail_mode != "default" else self.ctx.config.moderation_fail_mode
        await self.to_managers(s, ch, lambda lang: cards.api_failure_card(lang, ch, error, mode == "open"), include_system=True)

    async def unattributed(self, s: AsyncSession, ch: Channel) -> None:
        last = ch.last_unattributed_alert_at
        if last and (utcnow() - last).total_seconds() < 86400:
            return
        ch.last_unattributed_alert_at = utcnow()
        await s.flush()
        await self.to_managers(s, ch, lambda lang: cards.unattributed_card(lang, ch))

    async def ambiguous(self, s: AsyncSession, ch: Channel, sig: str, candidates: list[Admin]) -> None:
        if not self._allow(f"amb:{ch.id}:{sig}", 86400):
            return
        names = [a.display for a in candidates]
        await self.to_managers(s, ch, lambda lang: cards.ambiguous_card(lang, ch, sig, names))

    async def bot_rights_alert(self, s: AsyncSession, ch: Channel, missing: list[str]) -> None:
        if not self._allow(f"rights:{ch.id}:{','.join(missing)}", 1800):
            return
        await self.to_managers(s, ch, lambda lang: cards.bot_rights_card(lang, ch, missing))

    async def bot_removed(self, s: AsyncSession, ch: Channel, *, shield_members: int) -> None:
        await self.to_managers(s, ch, lambda lang: cards.bot_removed_card(lang, ch, shield_members), include_system=True)

    async def channel_pending(self, s: AsyncSession, ch: Channel, added_by: str, owner: str) -> None:
        await self.to_system(s, lambda lang: cards.pending_card(lang, ch, added_by, owner))

    async def channel_activated(self, s: AsyncSession, ch: Channel, *, managed: int, unmanaged: int) -> None:
        missing = self.ctx.channels.missing_bot_rights(ch)
        await self.to_managers(
            s, ch, lambda lang: cards.activated_card(lang, ch, missing_rights=missing, managed=managed, unmanaged=unmanaged)
        )

    async def channel_declined(self, s: AsyncSession, ch: Channel) -> None:
        if ch.added_by:
            await self.send(s, ch.added_by, lambda lang: (cards.declined_card(lang, ch), None))

    async def unauthorized_notice(self, s: AsyncSession, ch: Channel, added_by: int | None) -> None:
        delivered = False
        if added_by:
            delivered = await self.send(s, added_by, lambda lang: (cards.unauthorized_card(lang, ch), None)) is not None
        if not delivered and self.ctx.config.unauthorized_notice_in_channel and (ch.bot_rights or {}).get("can_post_messages"):
            text = t(self.ctx.config.default_language, "channel_notice_unauthorized")
            try:
                await tg(lambda: self.ctx.bot.send_message(ch.id, text), label="channelNotice")
            except TelegramAPIError as e:
                log.info("channel notice failed for %s: %s", ch.id, short_error(e))

    async def reattached(self, s: AsyncSession, ch: Channel) -> None:
        await self.to_managers(s, ch, lambda lang: cards.reattached_card(lang, ch))

    async def external_repromote(self, s: AsyncSession, ch: Channel, admin: Admin) -> None:
        if not self._allow(f"repro:{ch.id}:{admin.user_id}", 600):
            return
        await self.to_managers(s, ch, lambda lang: (cards.external_repromote_card(lang, ch, admin.display), None))
