"""SQLAlchemy 2.0 models. All datetimes are naive UTC. channel_id == 0 means "global"."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from vigil.core.timeutil import utcnow


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


# ── Users & roles ──────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    lang: Mapped[str] = mapped_column(String(5), default="en")
    role: Mapped[str] = mapped_column(String(16), default="user")  # owner | admin | user
    dm_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def display(self) -> str:
        name = " ".join(p for p in (self.first_name, self.last_name) if p) or (
            f"@{self.username}" if self.username else str(self.id)
        )
        return name


# ── Channels ───────────────────────────────────────────────────

class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending | active | suspended | revoked | detached
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    added_by: Mapped[int | None] = mapped_column(BigInteger)
    authorized_by: Mapped[int | None] = mapped_column(BigInteger)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    bot_rights: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    bot_status: Mapped[str] = mapped_column(String(16), default="unknown")  # administrator | member | left | kicked
    signatures_state: Mapped[str] = mapped_column(String(8), default="unknown")  # unknown | on | off
    last_unattributed_alert_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def link(self) -> str | None:
        if self.username:
            return f"https://t.me/{self.username}"
        return None


class ChannelPermission(Base):
    __tablename__ = "channel_permissions"
    __table_args__ = (UniqueConstraint("channel_id", "user_id", name="uq_channel_user_perm"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(16), default="manager")  # owner | manager
    granted_by: Mapped[int | None] = mapped_column(BigInteger)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ── Administrators ─────────────────────────────────────────────

class Admin(Base):
    __tablename__ = "admins"
    __table_args__ = (UniqueConstraint("channel_id", "user_id", name="uq_channel_admin"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(256), default="")
    custom_title: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    # active | suspended | shielded | unmanaged | removed | owner
    managed_by_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    rights: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime)
    demoted_at: Mapped[datetime | None] = mapped_column(DateTime)
    demote_reason: Mapped[str | None] = mapped_column(String(255))
    last_violation_id: Mapped[int | None] = mapped_column(Integer)
    violations_count: Mapped[int] = mapped_column(Integer, default=0)
    shield_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    @property
    def display(self) -> str:
        return self.full_name or (f"@{self.username}" if self.username else str(self.user_id))

    @property
    def signature_key(self) -> str:
        return (self.custom_title or self.full_name or "").strip()


class AdminSnapshot(Base):
    __tablename__ = "admin_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    admin_id: Mapped[int | None] = mapped_column(Integer)
    rights: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    custom_title: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(16), default="manual")  # violation | shield | manual
    taken_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime)
    restored_by: Mapped[int | None] = mapped_column(BigInteger)
    restore_error: Mapped[str | None] = mapped_column(String(255))


# ── Violations ─────────────────────────────────────────────────

class Violation(Base):
    __tablename__ = "violations"
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", "rule", name="uq_violation_msg_rule"),
        Index("ix_violation_channel_time", "channel_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    admin_id: Mapped[int | None] = mapped_column(Integer, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(32))     # link | mention | media | emoji | language | length | content | forward
    rule: Mapped[str] = mapped_column(String(64))     # e.g. link_guard:url
    detail: Mapped[str | None] = mapped_column(String(512))
    message_id: Mapped[int] = mapped_column(BigInteger)
    excerpt: Mapped[str | None] = mapped_column(Text)
    message_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    api_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    action: Mapped[str] = mapped_column(String(32), default="none")  # deleted | demoted | deleted+demoted | notified | failed
    snapshot_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime)
    restored_by: Mapped[int | None] = mapped_column(BigInteger)


# ── Settings ───────────────────────────────────────────────────

class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("channel_id", "key", name="uq_setting"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)  # 0 = global
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict[str, Any]] = mapped_column(JSON)  # {"v": ...}
    updated_by: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ── Shield Mode ────────────────────────────────────────────────

class ShieldSchedule(Base):
    __tablename__ = "shield_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(8), default="daily")  # daily | weekly
    start_time: Mapped[str] = mapped_column(String(5))  # HH:MM local
    end_time: Mapped[str] = mapped_column(String(5))    # HH:MM local (may be < start → crosses midnight)
    weekdays: Mapped[int] = mapped_column(Integer, default=127)  # bitmask Mon=1 … Sun=64
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ShieldSession(Base):
    __tablename__ = "shield_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(16), default="manual")  # manual | schedule
    schedule_id: Mapped[int | None] = mapped_column(Integer)
    started_by: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active | ending | ended | failed
    note: Mapped[str | None] = mapped_column(String(255))


class ShieldMember(Base):
    __tablename__ = "shield_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("shield_sessions.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    admin_id: Mapped[int | None] = mapped_column(Integer)
    snapshot_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="suspended")  # suspended | restored | failed | skipped
    error: Mapped[str | None] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime)


# ── Premium emoji ──────────────────────────────────────────────

class EmojiAllow(Base):
    __tablename__ = "emoji_allowlist"
    __table_args__ = (UniqueConstraint("channel_id", "custom_emoji_id", name="uq_emoji_allow"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)  # 0 = global
    custom_emoji_id: Mapped[str] = mapped_column(String(32), index=True)
    set_name: Mapped[str | None] = mapped_column(String(128))
    emoji: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(8), default="manual")  # manual | pack
    added_by: Mapped[int | None] = mapped_column(BigInteger)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EmojiPack(Base):
    __tablename__ = "emoji_packs"
    __table_args__ = (UniqueConstraint("channel_id", "set_name", name="uq_emoji_pack"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)
    set_name: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(128), default="")
    emoji_count: Mapped[int] = mapped_column(Integer, default=0)
    added_by: Mapped[int | None] = mapped_column(BigInteger)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ── Audit ──────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_channel_time", "channel_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(48), index=True)
    target_type: Mapped[str | None] = mapped_column(String(24))
    target_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ── Moderation usage (daily budget survives restarts) ─────────

class ModerationUsage(Base):
    __tablename__ = "moderation_usage"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD (UTC)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    last_model: Mapped[str | None] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
