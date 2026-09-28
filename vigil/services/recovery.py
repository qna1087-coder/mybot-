"""Startup reconciliation. The database is the source of truth; Telegram is re-verified."""

from __future__ import annotations

import asyncio
import logging

from vigil.core.timeutil import utcnow
from vigil.db.repo import audit
from vigil.db.repo import channels as ch_repo
from vigil.db.repo import shield as shield_repo
from vigil.services.context import Services

log = logging.getLogger("vigil.recovery")


class Recovery:
    def __init__(self, ctx: Services):
        self.ctx = ctx

    async def run(self) -> None:
        async with self.ctx.db.session() as s:
            await audit.log(s, "system.started", details_version=__import__("vigil").__version__)
        await self._verify_channels()
        await self._reconcile_sessions()
        async with self.ctx.db.session() as s:
            restored = await self.ctx.shield.retry_failed(s, only_fast=False)
            if restored:
                log.info("recovery restored %d administrators", restored)

    async def _verify_channels(self) -> None:
        async with self.ctx.db.session() as s:
            channels = await ch_repo.list_by_status(s, "active", "suspended")
            for ch in channels:
                before_missing = set(self.ctx.channels.missing_bot_rights(ch))
                rights = await self.ctx.admins.refresh_bot_rights(s, ch)
                if ch.bot_status in ("left", "kicked"):
                    await self.ctx.channels.detach(s, ch.id, status_now=ch.bot_status)
                    await self.ctx.notifier.bot_removed(s, ch, shield_members=0)
                    continue
                if rights is not None:
                    after_missing = set(self.ctx.channels.missing_bot_rights(ch))
                    if after_missing and after_missing != before_missing:
                        await self.ctx.notifier.bot_rights_alert(s, ch, sorted(after_missing))
                await asyncio.sleep(0.2)

    async def _reconcile_sessions(self) -> None:
        now = utcnow()
        async with self.ctx.db.session() as s:
            for sess in await shield_repo.list_active_sessions(s):
                if sess.status == "ending" or (sess.ends_at and sess.ends_at <= now):
                    log.info("recovery: ending shield session %s", sess.id)
                    await self.ctx.shield.end(s, sess, reason="recovery")
