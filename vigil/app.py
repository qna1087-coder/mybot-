"""Bootstrap: config → database → bot → services → dispatcher → recovery → scheduler → polling/webhook."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from vigil import __version__
from vigil.config import get_settings
from vigil.db.engine import Database
from vigil.services.admins import AdminService
from vigil.services.attribution import Attributor
from vigil.services.authorization import AccessService
from vigil.services.channels import ChannelService
from vigil.services.context import Services
from vigil.services.enforcement import Enforcer
from vigil.services.guard.media import MediaGroupTracker
from vigil.services.guard.moderation import ModerationClient
from vigil.services.guard.pipeline import GuardPipeline
from vigil.services.notifications import Notifier
from vigil.services.recovery import Recovery
from vigil.services.settings import ChannelSettingsService
from vigil.services.shield.scheduler import ShieldScheduler
from vigil.services.shield.sessions import ShieldService
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
from vigil.telegram.handlers.private import (
    settings as settings_h,
)
from vigil.telegram.middlewares.core import DbMiddleware, UserMiddleware

log = logging.getLogger("vigil")

ALLOWED_UPDATES = [
    "message",
    "callback_query",
    "channel_post",
    "edited_channel_post",
    "my_chat_member",
    "chat_member",
]


def build_services(cfg, db: Database, bot: Bot) -> Services:  # noqa: ANN001
    ctx = Services(config=cfg, db=db, bot=bot)
    ctx.settings = ChannelSettingsService(ctx)
    ctx.access = AccessService(ctx)
    ctx.channels = ChannelService(ctx)
    ctx.admins = AdminService(ctx)
    ctx.attributor = Attributor(ctx)
    ctx.notifier = Notifier(ctx)
    ctx.moderation = ModerationClient(ctx)
    ctx.media_groups = MediaGroupTracker(ttl_seconds=900)
    ctx.guard = GuardPipeline(ctx)
    ctx.enforcer = Enforcer(ctx)
    ctx.shield = ShieldService(ctx)
    ctx.scheduler = ShieldScheduler(ctx)
    ctx.recovery = Recovery(ctx)
    return ctx


def build_dispatcher(ctx: Services) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp["ctx"] = ctx
    dp.update.outer_middleware(DbMiddleware(ctx))
    dp.update.outer_middleware(UserMiddleware(ctx))
    for r in (
        start.router,
        channels.router,
        admins.router,
        guard.router,
        emoji.router,
        shield.router,
        activity.router,
        settings_h.router,
        system.router,
        posts.router,
        membership.router,
    ):
        dp.include_router(r)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("unhandled error: %s", event.exception)
        cb = event.update.callback_query
        if cb is not None:
            try:
                await cb.answer("Something went wrong. Recorded.", show_alert=False)
            except Exception:  # noqa: BLE001
                pass
        return True

    return dp


async def run() -> None:
    cfg = get_settings()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s · %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    log.info("Vigil %s starting", __version__)

    db = Database(cfg.database_url)
    await db.init()

    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    ctx = build_services(cfg, db, bot)
    ctx.bot_user = await bot.get_me()
    log.info("bot @%s (%s) · models: %s", ctx.bot_username, ctx.bot_id, ", ".join(cfg.model_chain[:3]) + " …")
    if not cfg.moderation_enabled:
        log.warning("moderation disabled: OPENROUTER_API_KEY is empty")

    dp = build_dispatcher(ctx)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Home"),
            BotCommand(command="id", description="Your Telegram ID"),
            BotCommand(command="cancel", description="Cancel current input"),
            BotCommand(command="help", description="Help"),
        ]
    )

    await ctx.recovery.run()
    ctx.scheduler.start()

    try:
        if cfg.use_webhook:
            await _run_webhook(cfg, bot, dp)
        else:
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES, handle_signals=True)
    finally:
        await ctx.scheduler.stop()
        await ctx.moderation.close()
        await db.dispose()
        await bot.session.close()
        log.info("Vigil stopped")


async def _run_webhook(cfg, bot: Bot, dp: Dispatcher) -> None:  # noqa: ANN001
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from aiohttp import web

    url = cfg.webhook_url.rstrip("/") + cfg.webhook_path
    await bot.set_webhook(url, secret_token=cfg.webhook_secret or None, allowed_updates=ALLOWED_UPDATES, drop_pending_updates=False)
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=cfg.webhook_secret or None).register(app, path=cfg.webhook_path)
    setup_application(app, dp, bot=bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, cfg.web_host, cfg.web_port)
    await site.start()
    log.info("webhook listening on %s:%s%s", cfg.web_host, cfg.web_port, cfg.webhook_path)
    try:
        await asyncio.Event().wait()
    finally:
        await bot.delete_webhook()
        await runner.cleanup()
