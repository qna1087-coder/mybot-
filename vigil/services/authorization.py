"""Who may do what. Every callback and every command asks this service first."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from vigil.db.repo import permissions as perm_repo
from vigil.db.repo import users as user_repo
from vigil.services.context import Services


class AccessService:
    def __init__(self, ctx: Services):
        self.ctx = ctx

    def is_system_owner(self, user_id: int) -> bool:
        return user_id == self.ctx.config.system_owner_id

    async def is_system_admin(self, s: AsyncSession, user_id: int) -> bool:
        if self.is_system_owner(user_id):
            return True
        user = await user_repo.get(s, user_id)
        return bool(user and user.role in ("owner", "admin"))

    async def channel_role(self, s: AsyncSession, user_id: int, channel_id: int) -> str | None:
        """'system' | 'owner' | 'manager' | None"""
        if await self.is_system_admin(s, user_id):
            return "system"
        return await perm_repo.get_role(s, channel_id, user_id)

    async def can_manage_channel(self, s: AsyncSession, user_id: int, channel_id: int) -> bool:
        return (await self.channel_role(s, user_id, channel_id)) is not None

    async def grant_system_admin(self, s: AsyncSession, user_id: int) -> None:
        await user_repo.set_role(s, user_id, "admin")

    async def revoke_system_admin(self, s: AsyncSession, user_id: int) -> None:
        if self.is_system_owner(user_id):
            return
        await user_repo.set_role(s, user_id, "user")
