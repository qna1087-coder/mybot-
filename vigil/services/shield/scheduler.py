"""A 30-second tick that reads the database and acts. Restart-safe by construction."""

from __future__ import annotations

import asyncio
import logging

from vigil.core.timeutil import utcnow
from vigil.db.repo import channels as ch_repo
from vigil.db.repo import shield as repo
from vigil.services.context import Services
from vigil.services.shield.schedules import window_at

log = logging.getLogger("vigil.scheduler")


class ShieldScheduler:
    def __init__(self, ctx: Services):
        self.ctx = ctx
        self._task: asyncio.Task | None = None
        self._tick = 0

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="vigil-scheduler")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        interval = max(self.ctx.config.shield_tick_seconds, 10)
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("scheduler tick failed")
            await asyncio.sleep(interval)

    async def tick(self) -> None:
        self._tick += 1
        await self._end_expired()
        await self._start_scheduled()
        await self._retry_failed()
        if self._tick % max(1, (self.ctx.config.admin_sync_minutes * 60) // max(self.ctx.config.shield_tick_seconds, 10)) == 0:
            await self._sync_admins()
        self.ctx.media_groups.purge()

    async def _end_expired(self) -> None:
        now = utcnow()
        async with self.ctx.db.session() as s:
            for sess in await repo.list_active_sessions(s):
                if sess.status == "active" and sess.ends_at and sess.ends_at <= now:
                    log.info("shield session %s expired → restoring", sess.id)
                    await self.ctx.shield.end(s, sess, reason="schedule")

    async def _start_scheduled(self) -> None:
        now = utcnow()
        async with self.ctx.db.session() as s:
            for sched in await repo.list_enabled_schedules(s):
                win = window_at(sched, now)
                if not win:
                    continue
                ch = await ch_repo.get(s, sched.channel_id)
                if ch is None or not ch.is_active:
                    continue
                if await repo.active_session(s, ch.id) is not None:
                    continue
                # If a session for this window already ran (manual stop), do not restart it.
                recent = await repo.list_recent_sessions(s, ch.id, limit=3)
                if any(r.schedule_id == sched.id and r.started_at >= win[0] for r in recent):
                    continue
                log.info("schedule %s active → starting shield for %s", sched.id, ch.id)
                try:
                    await self.ctx.shield.start(s, ch, by=None, trigger="schedule", ends_at=win[1], schedule_id=sched.id)
                except Exception as e:  # noqa: BLE001
                    log.warning("scheduled start failed for %s: %s", ch.id, e)
                    await self.ctx.notifier.bot_rights_alert(s, ch, ["can_promote_members"])

    async def _retry_failed(self) -> None:
        async with self.ctx.db.session() as s:
            await self.ctx.shield.retry_failed(s, only_fast=(self._tick % 10 != 0))

    async def _sync_admins(self) -> None:
        async with self.ctx.db.session() as s:
            for ch in await ch_repo.list_by_status(s, "active"):
                await self.ctx.channels.sync_admins(s, ch)
                await asyncio.sleep(0.3)
