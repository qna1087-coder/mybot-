"""Compact callback payloads (Telegram caps callback_data at 64 bytes).

Nothing here is trusted: every handler re-checks the user's permission on the server.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class Nav(CallbackData, prefix="n"):
    """Navigate to a screen."""

    s: str  # screen id
    c: int = 0  # channel id
    a: str = ""  # argument (admin id, schedule id, filter …)
    p: int = 0  # page


class Act(CallbackData, prefix="x"):
    """Perform an action."""

    a: str  # action id
    c: int = 0  # channel id
    t: str = ""  # target
    v: str = ""  # value / "ok" for confirmed


# Screen ids
S_HOME = "home"
S_CHANNELS = "chs"
S_DASH = "ch"
S_ADMINS = "adm"
S_ADMIN = "admd"
S_ADD_ADMIN = "adda"
S_ADD_PRESET = "addp"
S_GUARD = "grd"
S_MEDIA = "med"
S_CATEGORIES = "cat"
S_EMOJI = "emo"
S_EMOJI_IDS = "emoi"
S_SHIELD = "shd"
S_SHIELD_START = "shst"
S_SCHEDULES = "shs"
S_SCHEDULE = "shsd"
S_EXEMPT = "shx"
S_HISTORY = "shh"
S_ACTIVITY = "act"
S_VIOLATIONS = "vio"
S_VIOLATION = "viod"
S_SETTINGS = "set"
S_MANAGERS = "mgr"
S_SYSTEM = "sys"
S_PENDING = "pend"
S_ALL_CHANNELS = "sysc"
S_SYS_ADMINS = "sysa"
S_HEALTH = "hlth"
S_HELP = "help"
S_LANG = "lang"
S_BOT_RIGHTS = "brt"

# Action ids
A_RESTORE_VIOLATION = "rsv"  # t = violation id
A_RETRY_SHIELD = "rsh"  # t = session id
A_ACTIVATE = "cha"  # t = channel id (in c)
A_DECLINE = "chd"
A_CH_SUSPEND = "chs"
A_CH_RESUME = "chr"
A_CH_REVOKE = "chx"
A_ADMIN_SUSPEND = "asu"  # t = admin id
A_ADMIN_RESTORE = "ars"
A_ADMIN_REMOVE = "arm"
A_ADMIN_EXEMPT = "aex"
A_ADMIN_RESET = "arz"
A_ADMIN_SYNC = "asy"
A_ADD_PRESET = "app"  # t = preset
A_ADD_CONFIRM = "apc"
A_TOGGLE = "tg"  # t = setting key
A_CYCLE = "cy"  # t = setting key (cycles enumerated values)
A_MEDIA_POLICY = "mp"  # t = media type
A_MEDIA_COUNT = "mc"  # v = +/-
A_CATEGORY = "cg"  # t = category
A_LIMIT_SET = "lim"
A_EMOJI_REMOVE_PACK = "erp"  # t = set name
A_EMOJI_SYNC_PACK = "esp"
A_EMOJI_REMOVE_ID = "eri"  # t = emoji id
A_EMOJI_ADD_PACK = "eap"
A_EMOJI_ADD_ONE = "eao"
A_EMOJI_CHECK = "eck"
A_SHIELD_START = "sst"  # t = duration minutes or "manual" / "custom"
A_SHIELD_STOP = "ssp"
A_SCHEDULE_ADD = "sad"  # t = daily | weekly
A_SCHEDULE_DEL = "sde"  # t = schedule id
A_SCHEDULE_TOGGLE = "sto"
A_SCHEDULE_DAY = "sdy"  # t = schedule id, v = weekday index
A_EXEMPT_TOGGLE = "sxt"  # t = admin id
A_SET_LANG = "lng"  # t = en | ar
A_SET_TZ = "tz"
A_MANAGER_ADD = "mga"
A_MANAGER_DEL = "mgd"  # t = user id
A_SYSADMIN_ADD = "saa"
A_SYSADMIN_DEL = "sad2"  # t = user id
A_ADOPT = "adp"  # t = admin id
A_CANCEL = "cxl"
A_NOOP = "nop"
