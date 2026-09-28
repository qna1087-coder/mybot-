"""Administrator rights: the exact Bot API field set, snapshots, and presets.

Bot API 10.3 — nineteen boolean rights on promoteChatMember. We always snapshot the full
set so a restore is precise, and we always intersect with the bot's own rights because
Telegram only lets a bot grant a subset of what it holds itself.
"""

from __future__ import annotations

from typing import Any

ADMIN_RIGHT_FIELDS: tuple[str, ...] = (
    "is_anonymous",
    "can_manage_chat",
    "can_delete_messages",
    "can_manage_video_chats",
    "can_restrict_members",
    "can_promote_members",
    "can_change_info",
    "can_invite_users",
    "can_post_stories",
    "can_edit_stories",
    "can_delete_stories",
    "can_post_messages",
    "can_edit_messages",
    "can_pin_messages",
    "can_manage_topics",
    "can_manage_direct_messages",
    "can_manage_tags",
    "can_send_welcome_messages",
)

# Rights the bot itself must hold to operate.
REQUIRED_BOT_RIGHTS: tuple[str, ...] = ("can_promote_members", "can_delete_messages")
OPTIONAL_BOT_RIGHTS: tuple[str, ...] = ("can_post_messages", "can_invite_users")

NO_RIGHTS: dict[str, bool] = dict.fromkeys(ADMIN_RIGHT_FIELDS, False)

PRESETS: dict[str, dict[str, bool]] = {
    "publisher": {
        **NO_RIGHTS,
        "can_post_messages": True,
        "can_edit_messages": True,
        "can_delete_messages": True,
    },
    "editor": {
        **NO_RIGHTS,
        "can_post_messages": True,
        "can_edit_messages": True,
        "can_delete_messages": True,
        "can_post_stories": True,
        "can_edit_stories": True,
        "can_delete_stories": True,
        "can_pin_messages": True,
    },
    "moderator": {
        **NO_RIGHTS,
        "can_delete_messages": True,
        "can_manage_direct_messages": True,
        "can_invite_users": True,
    },
    "full": {
        **dict.fromkeys(ADMIN_RIGHT_FIELDS, True),
        "is_anonymous": False,
        "can_promote_members": False,
    },
}

RIGHT_LABELS_EN = {
    "is_anonymous": "Anonymous",
    "can_manage_chat": "Manage channel",
    "can_delete_messages": "Delete messages",
    "can_manage_video_chats": "Manage live streams",
    "can_restrict_members": "Restrict members",
    "can_promote_members": "Add new admins",
    "can_change_info": "Change info",
    "can_invite_users": "Invite users",
    "can_post_stories": "Post stories",
    "can_edit_stories": "Edit stories",
    "can_delete_stories": "Delete stories",
    "can_post_messages": "Post messages",
    "can_edit_messages": "Edit messages",
    "can_pin_messages": "Pin messages",
    "can_manage_topics": "Manage topics",
    "can_manage_direct_messages": "Manage direct messages",
    "can_manage_tags": "Manage tags",
    "can_send_welcome_messages": "Welcome messages",
}

RIGHT_LABELS_AR = {
    "is_anonymous": "مجهول",
    "can_manage_chat": "إدارة القناة",
    "can_delete_messages": "حذف الرسائل",
    "can_manage_video_chats": "إدارة البث",
    "can_restrict_members": "تقييد الأعضاء",
    "can_promote_members": "إضافة مشرفين",
    "can_change_info": "تغيير المعلومات",
    "can_invite_users": "دعوة مستخدمين",
    "can_post_stories": "نشر القصص",
    "can_edit_stories": "تعديل القصص",
    "can_delete_stories": "حذف القصص",
    "can_post_messages": "نشر الرسائل",
    "can_edit_messages": "تعديل الرسائل",
    "can_pin_messages": "تثبيت الرسائل",
    "can_manage_topics": "إدارة المواضيع",
    "can_manage_direct_messages": "إدارة الرسائل المباشرة",
    "can_manage_tags": "إدارة الوسوم",
    "can_send_welcome_messages": "رسائل الترحيب",
}


def rights_from_member(member: Any) -> dict[str, bool]:
    """Extract the full rights dict from a ChatMemberAdministrator (or owner → all True)."""
    status = getattr(member, "status", None)
    if status == "creator":
        return {**dict.fromkeys(ADMIN_RIGHT_FIELDS, True), "is_anonymous": bool(getattr(member, "is_anonymous", False))}
    out: dict[str, bool] = {}
    for f in ADMIN_RIGHT_FIELDS:
        out[f] = bool(getattr(member, f, False) or False)
    return out


def normalize_rights(rights: dict[str, Any] | None) -> dict[str, bool]:
    base = dict(NO_RIGHTS)
    if rights:
        for k, v in rights.items():
            if k in base:
                base[k] = bool(v)
    return base


def intersect_with_bot(rights: dict[str, bool], bot_rights: dict[str, bool] | None) -> tuple[dict[str, bool], list[str]]:
    """Keep only rights the bot can grant. Returns (grantable, dropped)."""
    if not bot_rights:
        return dict(rights), []
    granted: dict[str, bool] = {}
    dropped: list[str] = []
    for f in ADMIN_RIGHT_FIELDS:
        want = bool(rights.get(f))
        if f == "is_anonymous":
            granted[f] = want
            continue
        can = bool(bot_rights.get(f))
        if want and not can:
            dropped.append(f)
            granted[f] = False
        else:
            granted[f] = want
    return granted, dropped


def has_any_right(rights: dict[str, bool] | None) -> bool:
    if not rights:
        return False
    return any(v for k, v in rights.items() if k != "is_anonymous")


def enabled_rights(rights: dict[str, bool] | None) -> list[str]:
    return [f for f in ADMIN_RIGHT_FIELDS if rights and rights.get(f)]
