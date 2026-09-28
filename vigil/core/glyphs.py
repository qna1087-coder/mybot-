"""The visual language of Vigil.

One glyph per state, used identically on every screen. Emoji are deliberately absent:
these symbols read cleanly in both LTR and RTL text and never compete with content.
"""

ACTIVE = "●"      # on / protected / active
OFF = "○"         # off / offline / suspended
SHIELDED = "◉"    # temporarily suspended by Shield Mode
WAITING = "◇"     # pending / scheduled / details
ATTENTION = "!"   # needs a human decision
SPARK = "✦"       # highlight (used once: the home title)
RESTORE = "↻"     # restore / retry / refresh
OPEN = "↗"        # open / external
LIVE = "⌁"        # last event / live signal
BACK = "‹"
FORWARD = "›"
DOT = "·"
RULE = "─" * 16
ARROW = "→"

STATUS_GLYPH = {
    "active": ACTIVE,
    "on": ACTIVE,
    "protected": ACTIVE,
    "off": OFF,
    "offline": OFF,
    "suspended": OFF,
    "shielded": SHIELDED,
    "pending": WAITING,
    "waiting": WAITING,
    "scheduled": WAITING,
    "attention": ATTENTION,
    "unmanaged": ATTENTION,
    "failed": ATTENTION,
}


def glyph(state: str) -> str:
    return STATUS_GLYPH.get(state, WAITING)
