"""Shared helpers for the private control surface."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core import glyphs as G
from vigil.core.rights import (
    OPTIONAL_BOT_RIGHTS,
    REQUIRED_BOT_RIGHTS,
    RIGHT_LABELS_AR,
    RIGHT_LABELS_EN,
)
from vigil.core.timeutil import fmt_datetime, humanize_ago
from vigil.db.models import Channel, User
from vigil.db.repo import admins as admin_repo
from vigil.db.repo import audit as audit_repo
from vigil.db.repo import channels as ch_repo
from vigil.services.context import Services
from vigil.telegram.callbacks import (
    A_CANCEL,
    S_ACTIVITY,
    S_ADMINS,
    S_BOT_RIGHTS,
    S_CHANNELS,
    S_DASH,
    S_EMOJI,
    S_GUARD,
    S_HELP,
    S_SETTINGS,
    S_SHIELD,
    S_SYSTEM,
    Act,
    Nav,
)
from vigil.telegram.ui.screens import compose, kb, nav, toast
from vigil.telegram.ui.texts import en, esc, t


class Input(StatesGroup):
    admin_user = State()
    limit = State()
    emoji_pack = State()
    emoji_one = State()
    emoji_check = State()
    duration = State()
    sched_start = State()
    sched_end = State()
    tz = State()
    manager_user = State()
    sysadmin_user = State()


@dataclass
class UserRef:
    user_id: int
    username: str | None = None
    name: str = ""
    is_bot: bool = False


_ID_RE = re.compile(r"^\s*(-?\d{5,15})\s*$")


def resolve_user_ref(message: Message) -> UserRef | None:
    """From a shared user, a forwarded message, a text mention, or a numeric ID."""
    shared = getattr(message, "users_shared", None)
    if shared is not None and shared.users:
        u = shared.users[0]
        name = " ".join(p for p in (u.first_name, u.last_name) if p)
        return UserRef(user_id=u.user_id, username=u.username, name=name)
    origin = getattr(message, "forward_origin", None)
    if origin is not None:
        sender = getattr(origin, "sender_user", None)
        if sender is not None:
            return UserRef(user_id=sender.id, username=sender.username, name=sender.full_name, is_bot=sender.is_bot)
        return None
    for e in message.entities or []:
        if e.type == "text_mention" and e.user is not None:
            return UserRef(user_id=e.user.id, username=e.user.username, name=e.user.full_name, is_bot=e.user.is_bot)
    text = (message.text or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    m = _ID_RE.match(text)
    if m:
        uid = int(m.group(1))
        if uid > 0:
            return UserRef(user_id=uid)
    return None


def right_labels(lang: str, rights: list[str]) -> str:
    table = RIGHT_LABELS_AR if lang == "ar" else RIGHT_LABELS_EN
    return ", ".join(table.get(r, r) for r in rights) or t(lang, "none")


def audit_label(lang: str, action: str) -> str:
    key = f"au_{action}"
    if key in en.T:
        return t(lang, key)
    return action.replace(".", " · ").replace("_", " ")


def cancel_kb(lang: str) -> InlineKeyboardMarkup:
    return kb([[(t(lang, "cancel"), Act(a=A_CANCEL).pack())]])


async def deny(event: CallbackQuery | Message, lang: str) -> None:
    if isinstance(event, CallbackQuery):
        await toast(event, t(lang, "toast_not_permitted"), alert=True)
    else:
        await event.answer(t(lang, "not_permitted"))


async def guard_channel(
    event: CallbackQuery | Message, ctx: Services, s: AsyncSession, user: User, channel_id: int, lang: str
) -> Channel | None:
    ch = await ch_repo.get(s, channel_id) if channel_id else None
    if ch is None or not await ctx.access.can_manage_channel(s, user.id, channel_id):
        await audit_repo.log(s, "access.denied", channel_id=channel_id or 0, actor=user.id)
        await deny(event, lang)
        return None
    return ch


async def guard_system(event: CallbackQuery | Message, ctx: Services, s: AsyncSession, user: User, lang: str) -> bool:
    if await ctx.access.is_system_admin(s, user.id):
        return True
    await audit_repo.log(s, "access.denied", actor=user.id, scope="system")
    await deny(event, lang)
    return False


def channel_state(lang: str, ch: Channel) -> str:
    glyph = {
        "active": G.ACTIVE,
        "pending": G.WAITING,
        "suspended": G.OFF,
        "revoked": G.OFF,
        "detached": G.ATTENTION,
    }.get(ch.status, G.WAITING)
    return f"{glyph} {t(lang, 'ch_status_' + ch.status)}"


def title_of(ch: Channel) -> str:
    return esc(ch.title or str(ch.id))


# ── dashboard ──────────────────────────────────────────────────

async def dashboard(ctx: Services, s: AsyncSession, ch: Channel, lang: str, *, is_system: bool) -> tuple[str, InlineKeyboardMarkup]:
    counts = await admin_repo.count_by_status(s, ch.id)
    active = counts.get("active", 0)
    shielded = counts.get("shielded", 0)
    suspended = counts.get("suspended", 0)
    unmanaged = counts.get("unmanaged", 0)
    missing = ctx.channels.missing_bot_rights(ch)
    settings = await ctx.settings.get(s, ch.id)
    shield = await ctx.shield.status(s, ch)

    channel_lines = [channel_state(lang, ch)]
    if ch.status == "detached":
        channel_lines.append(f"{G.ATTENTION} {t(lang, 'attn_detached')}")
    elif missing:
        channel_lines.append(f"{G.ATTENTION} {t(lang, 'attn_bot_rights', rights=right_labels(lang, missing))}")
    if ch.signatures_state == "off":
        channel_lines.append(f"{G.ATTENTION} {t(lang, 'attn_signatures')}")
    if unmanaged:
        channel_lines.append(f"{G.ATTENTION} {t(lang, 'attn_unmanaged', n=unmanaged)}")

    admin_bits = [f"{G.ACTIVE} {t(lang, 'admins_summary', active=active)}"]
    if shielded:
        admin_bits.append(f"{G.SHIELDED} {t(lang, 'admins_shielded', n=shielded)}")
    if suspended:
        admin_bits.append(f"{G.OFF} {t(lang, 'admins_suspended', n=suspended)}")
    if unmanaged:
        admin_bits.append(f"{G.ATTENTION} {t(lang, 'admins_attention', n=unmanaged)}")

    if shield.session is not None:
        if shield.session.status == "ending":
            shield_line = f"{G.SHIELDED} {t(lang, 'shd_ending')}"
        elif shield.session.ends_at:
            shield_line = f"{G.SHIELDED} {t(lang, 'shield_until', until=fmt_datetime(shield.session.ends_at, ch.timezone))}"
        else:
            shield_line = f"{G.SHIELDED} {t(lang, 'shield_manual')}"
    else:
        shield_line = f"{G.OFF} {t(lang, 'shield_offline')}"
        if shield.next_start:
            shield_line += f"  {G.DOT}  {t(lang, 'shield_next', when=fmt_datetime(shield.next_start, ch.timezone))}"

    layers = []
    if settings.links_guard:
        layers.append(t(lang, "layer_links"))
    if settings.mentions_guard:
        layers.append(t(lang, "layer_mentions"))
    if settings.media_guard:
        layers.append(t(lang, "layer_media"))
    if settings.emoji_guard:
        layers.append(t(lang, "layer_emoji"))
    if settings.language_guard:
        layers.append(t(lang, "layer_language"))
    if settings.english_moderation and ctx.moderation.enabled:
        layers.append(t(lang, "layer_moderation"))
    if settings.guard_enabled and ch.is_active:
        guard_line = f"{G.ACTIVE} {t(lang, 'guard_on')}  {G.DOT}  " + "  ".join(layers)
    else:
        guard_line = f"{G.OFF} {t(lang, 'guard_off')}"

    footer = None
    for entry in await audit_repo.list_entries(s, channel_id=ch.id, limit=8):
        if entry.action.startswith(("violation", "admin.", "shield.", "channel.")) and entry.action != "channel.bot_rights_changed":
            label = audit_label(lang, entry.action)
            det = entry.details or {}
            extra = det.get("kind") or det.get("reason") or ""
            if extra:
                label += f" — {t(lang, 'kind_' + extra) if ('kind_' + extra) in en.T else esc(str(extra)[:40])}"
            footer = f"{G.LIVE} {t(lang, 'last_event', ago=humanize_ago(entry.created_at, lang), text=label)}"
            break

    text = compose(
        f"{G.SPARK} {t(lang, 'app')} {G.DOT} {title_of(ch)}",
        (t(lang, "sec_channel"), channel_lines),
        (t(lang, "sec_admins"), ["  ".join(admin_bits)]),
        (t(lang, "sec_shield"), [shield_line]),
        (t(lang, "sec_guard"), [guard_line]),
        footer,
    )
    rows: list[list[tuple[str, str]]] = [
        [(t(lang, "btn_admins"), Nav(s=S_ADMINS, c=ch.id).pack()), (t(lang, "btn_shield"), Nav(s=S_SHIELD, c=ch.id).pack())],
        [(t(lang, "btn_guard"), Nav(s=S_GUARD, c=ch.id).pack()), (t(lang, "btn_emoji"), Nav(s=S_EMOJI, c=ch.id).pack())],
        [(t(lang, "btn_activity"), Nav(s=S_ACTIVITY, c=ch.id).pack()), (t(lang, "btn_settings"), Nav(s=S_SETTINGS, c=ch.id).pack())],
    ]
    if missing or ch.status == "detached":
        rows.append([(t(lang, "btn_bot_rights"), Nav(s=S_BOT_RIGHTS, c=ch.id).pack())])
    rows.append(nav(lang, back=Nav(s=S_CHANNELS).pack(), refresh=Nav(s=S_DASH, c=ch.id).pack()))
    return text, kb(rows)


async def home(ctx: Services, s: AsyncSession, user: User, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    is_system = await ctx.access.is_system_admin(s, user.id)
    channels = await ch_repo.list_all(s) if is_system else await ch_repo.list_for_user(s, user.id)
    channels = [c for c in channels if c.status != "revoked"] if is_system else channels
    if len(channels) == 1 and not is_system:
        return await dashboard(ctx, s, channels[0], lang, is_system=False)
    if not channels:
        text = compose(
            t(lang, "welcome_title"),
            t(lang, "welcome_body", bot=ctx.bot_username or "bot"),
            t(lang, "welcome_no_channels") if not is_system else None,
        )
        rows: list[list[tuple[str, str]]] = []
        if is_system:
            rows.append([(t(lang, "btn_system"), Nav(s=S_SYSTEM).pack())])
        rows.append([(t(lang, "btn_help"), Nav(s=S_HELP).pack())])
        return text, kb(rows)
    active = sum(1 for c in channels if c.is_active)
    text = compose(
        t(lang, "home_title"),
        (t(lang, "home_channels"), [f"{G.ACTIVE} {t(lang, 'home_channels_line', n=active)}", t(lang, "home_pick")]),
    )
    rows = [[(f"{channel_state(lang, c)[0]} {esc(c.title)[:40]}", Nav(s=S_DASH, c=c.id).pack())] for c in channels[:10]]
    tail: list[tuple[str, str]] = []
    if len(channels) > 10:
        tail.append((t(lang, "btn_channels"), Nav(s=S_CHANNELS).pack()))
    if is_system:
        tail.append((t(lang, "btn_system"), Nav(s=S_SYSTEM).pack()))
    tail.append((t(lang, "btn_help"), Nav(s=S_HELP).pack()))
    rows.append(tail)
    return text, kb(rows)


async def bot_rights_screen(ctx: Services, s: AsyncSession, ch: Channel, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    await ctx.admins.refresh_bot_rights(s, ch)
    table = RIGHT_LABELS_AR if lang == "ar" else RIGHT_LABELS_EN
    rights = ch.bot_rights or {}
    if ch.bot_status != "administrator":
        body: Any = [f"{G.ATTENTION} {t(lang, 'brt_not_admin')}"]
        text = compose(t(lang, "brt_title"), (title_of(ch), body))
    else:
        req = [f"{G.ACTIVE if rights.get(r) else G.ATTENTION} {table.get(r, r)}" for r in REQUIRED_BOT_RIGHTS]
        opt = [f"{G.ACTIVE if rights.get(r) else G.OFF} {table.get(r, r)}" for r in OPTIONAL_BOT_RIGHTS]
        missing = ctx.channels.missing_bot_rights(ch)
        text = compose(
            t(lang, "brt_title"),
            t(lang, "brt_intro"),
            (t(lang, "brt_required"), req),
            (t(lang, "brt_optional"), opt),
            footer=t(lang, "brt_missing_hint") if missing else None,
        )
    return text, kb([nav(lang, back=Nav(s=S_DASH, c=ch.id).pack(), refresh=Nav(s=S_BOT_RIGHTS, c=ch.id).pack())])
