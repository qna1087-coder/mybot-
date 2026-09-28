"""Who wrote this channel post? Telegram gives bots only the author signature."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.models import Admin, Channel
from vigil.services.context import Services


@dataclass
class Attribution:
    status: str  # ok | owner | self | unsigned | unknown | ambiguous
    admin: Admin | None = None
    signature: str | None = None
    candidates: list[Admin] | None = None


class Attributor:
    def __init__(self, ctx: Services):
        self.ctx = ctx

    async def attribute(self, s: AsyncSession, ch: Channel, message: Any) -> Attribution:
        via = getattr(message, "via_bot", None)
        if via is not None and via.id == self.ctx.bot_id:
            return Attribution(status="self")
        sig = (message.author_signature or "").strip()
        if not sig:
            if ch.signatures_state != "off":
                ch.signatures_state = "off"
                await s.flush()
            return Attribution(status="unsigned")
        if ch.signatures_state != "on":
            ch.signatures_state = "on"
            await s.flush()
        if self.ctx.bot_user and sig in {self.ctx.bot_user.first_name, self.ctx.bot_user.full_name}:
            return Attribution(status="self", signature=sig)
        registry = await self.ctx.channels.signature_registry(s, ch.id)
        candidates = registry.get(sig) or []
        if not candidates:
            # A freshly promoted admin we have not synced yet? Sync once and retry.
            await self.ctx.channels.sync_admins(s, ch)
            registry = await self.ctx.channels.signature_registry(s, ch.id)
            candidates = registry.get(sig) or []
        unique = {a.user_id: a for a in candidates}
        if not unique:
            return Attribution(status="unknown", signature=sig)
        if len(unique) > 1:
            return Attribution(status="ambiguous", signature=sig, candidates=list(unique.values()))
        admin = next(iter(unique.values()))
        if admin.status == "owner":
            return Attribution(status="owner", admin=admin, signature=sig)
        return Attribution(status="ok", admin=admin, signature=sig)
