"""Turn a verdict into consequences: delete, snapshot + demote, record, notify. Idempotent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.errors import AdminNotManaged, BotRightsMissing, TelegramFailure
from vigil.core.retry import is_message_gone, short_error, tg
from vigil.db.models import Admin, Channel, Violation
from vigil.db.repo import audit
from vigil.db.repo import violations as vio_repo
from vigil.services.attribution import Attribution
from vigil.services.context import Services
from vigil.services.guard.verdict import Verdict
from vigil.services.settings import ChannelSettings

log = logging.getLogger("vigil.enforce")


class Enforcer:
    def __init__(self, ctx: Services):
        self.ctx = ctx
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, channel_id: int) -> asyncio.Lock:
        return self._locks.setdefault(channel_id, asyncio.Lock())

    async def apply(
        self,
        s: AsyncSession,
        ch: Channel,
        message: Any,
        verdict: Verdict,
        attribution: Attribution,
        settings: ChannelSettings,
    ) -> Violation | None:
        async with self._lock(ch.id):
            if await vio_repo.find(s, ch.id, message.message_id, verdict.rule):
                return None  # duplicate update

            admin: Admin | None = attribution.admin
            deleted = False
            if settings.delete_offending_message and (ch.bot_rights or {}).get("can_delete_messages"):
                deleted = await self._delete(ch.id, {message.message_id, *verdict.related_message_ids})

            action = settings.length_action if verdict.is_length else settings.violation_action
            want_demote = action == "demote"
            demoted = False
            could_not: str | None = None
            snapshot_id: int | None = None

            if want_demote:
                if attribution.status in ("unsigned", "unknown", "ambiguous"):
                    could_not = "unattributed"
                elif attribution.status == "owner" or (admin and admin.status == "owner"):
                    could_not = "owner"
                elif admin is None:
                    could_not = "unattributed"
                elif admin.status in ("suspended", "shielded", "removed"):
                    could_not = "already"
                elif not admin.managed_by_bot:
                    could_not = "unmanaged"
                else:
                    try:
                        snap = await self.ctx.admins.demote(
                            s, ch, admin, reason=self._reason(verdict), snapshot_reason="violation"
                        )
                        snapshot_id = snap.id
                        demoted = True
                    except AdminNotManaged:
                        could_not = "unmanaged"
                    except BotRightsMissing:
                        could_not = "bot_rights"
                    except TelegramFailure as e:
                        could_not = "telegram"
                        await audit.log(s, "telegram.failure", channel_id=ch.id, op="demote", error=str(e))

            parts = [p for p in (("deleted" if deleted else None), ("demoted" if demoted else None)) if p]
            action_str = "+".join(parts) if parts else ("notified" if not want_demote else "failed")

            v = await vio_repo.create(
                s,
                channel_id=ch.id,
                admin_id=admin.id if admin else None,
                user_id=admin.user_id if admin else None,
                username=admin.username if admin else None,
                display_name=self._display_name(attribution),
                kind=verdict.kind,
                rule=verdict.rule,
                detail=(verdict.detail or "")[:512],
                message_id=message.message_id,
                excerpt=verdict.excerpt,
                message_json=self._message_meta(message),
                api_result=verdict.api_result,
                action=action_str,
                snapshot_id=snapshot_id,
            )
            if admin is not None:
                admin.violations_count = (admin.violations_count or 0) + 1
                admin.last_violation_id = v.id
                if demoted:
                    admin.demote_reason = self._reason(verdict)
            await audit.log(
                s, "violation", channel_id=ch.id, target_type="user", target_id=admin.user_id if admin else None,
                kind=verdict.kind, rule=verdict.rule, message_id=message.message_id, taken=action_str,
                could_not=could_not, violation_id=v.id,
            )
            await s.flush()
            await self.ctx.notifier.violation(
                s, ch, v, admin, attribution=attribution, demoted=demoted, deleted=deleted,
                could_not=could_not, notify_system=bool(settings.notify_system_owner),
            )
            return v

    async def _delete(self, chat_id: int, message_ids: set[int]) -> bool:
        ids = sorted(message_ids)
        try:
            if len(ids) == 1:
                await tg(lambda: self.ctx.bot.delete_message(chat_id, ids[0]), label="deleteMessage")
            else:
                await tg(lambda: self.ctx.bot.delete_messages(chat_id, ids[:100]), label="deleteMessages")
            return True
        except TelegramAPIError as e:
            if is_message_gone(e):
                return True
            log.warning("delete failed in %s: %s", chat_id, short_error(e))
            return False

    @staticmethod
    def _reason(verdict: Verdict) -> str:
        return f"{verdict.kind}: {verdict.detail}"[:255] if verdict.detail else verdict.kind

    @staticmethod
    def _display_name(attribution: Attribution) -> str | None:
        if attribution.admin is not None:
            return attribution.admin.display
        return attribution.signature

    @staticmethod
    def _message_meta(message: Any) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "message_id": message.message_id,
            "date": message.date.isoformat() if getattr(message, "date", None) else None,
            "author_signature": message.author_signature,
            "media_group_id": message.media_group_id,
            "has_text": bool(message.text),
            "has_caption": bool(message.caption),
        }
        ents = list(message.entities or []) + list(message.caption_entities or [])
        if ents:
            meta["entities"] = [{"type": e.type, "offset": e.offset, "length": e.length} for e in ents[:20]]
        for attr in ("photo", "video", "document", "animation", "sticker", "voice", "audio", "video_note"):
            if getattr(message, attr, None) is not None:
                meta["media"] = attr
                break
        return meta
