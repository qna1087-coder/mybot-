"""Shared service registry. Services receive the context and resolve peers lazily at call time."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from vigil.core.timeutil import utcnow

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import User as TgUser

    from vigil.config import Settings
    from vigil.db.engine import Database
    from vigil.services.admins import AdminService
    from vigil.services.attribution import Attributor
    from vigil.services.authorization import AccessService
    from vigil.services.channels import ChannelService
    from vigil.services.enforcement import Enforcer
    from vigil.services.guard.media import MediaGroupTracker
    from vigil.services.guard.moderation import ModerationClient
    from vigil.services.guard.pipeline import GuardPipeline
    from vigil.services.notifications import Notifier
    from vigil.services.recovery import Recovery
    from vigil.services.settings import ChannelSettingsService
    from vigil.services.shield.scheduler import ShieldScheduler
    from vigil.services.shield.sessions import ShieldService


@dataclass
class Services:
    config: Settings
    db: Database
    bot: Bot
    started_at: datetime = field(default_factory=utcnow)
    bot_user: TgUser | None = None

    settings: ChannelSettingsService = None  # type: ignore[assignment]
    access: AccessService = None  # type: ignore[assignment]
    channels: ChannelService = None  # type: ignore[assignment]
    admins: AdminService = None  # type: ignore[assignment]
    attributor: Attributor = None  # type: ignore[assignment]
    notifier: Notifier = None  # type: ignore[assignment]
    moderation: ModerationClient = None  # type: ignore[assignment]
    media_groups: MediaGroupTracker = None  # type: ignore[assignment]
    guard: GuardPipeline = None  # type: ignore[assignment]
    enforcer: Enforcer = None  # type: ignore[assignment]
    shield: ShieldService = None  # type: ignore[assignment]
    scheduler: ShieldScheduler = None  # type: ignore[assignment]
    recovery: Recovery = None  # type: ignore[assignment]

    runtime: dict[str, Any] = field(default_factory=dict)

    @property
    def bot_id(self) -> int:
        return self.bot_user.id if self.bot_user else 0

    @property
    def bot_username(self) -> str:
        return (self.bot_user.username or "") if self.bot_user else ""
