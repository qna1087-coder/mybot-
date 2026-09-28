"""Fast, local script detection — no network, no third-party models.

Arabic script (including Persian/Urdu letters used in Iraqi dialect writing) is never sent
anywhere. Latin text is what the moderation API sees. Any other script is a local verdict.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

_ARABIC_RANGES = (
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)
_LATIN_RANGES = (
    (0x0041, 0x005A),
    (0x0061, 0x007A),
    (0x00C0, 0x024F),  # Latin-1 Supplement, Extended-A/B
    (0x1E00, 0x1EFF),  # Latin Extended Additional
)


def _in_ranges(cp: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def is_letter(ch: str) -> bool:
    return unicodedata.category(ch).startswith("L")


def script_of(ch: str) -> str | None:
    """'arabic' | 'latin' | 'other' | None (not a letter)."""
    if not is_letter(ch):
        return None
    cp = ord(ch)
    if _in_ranges(cp, _ARABIC_RANGES):
        return "arabic"
    if _in_ranges(cp, _LATIN_RANGES):
        return "latin"
    return "other"


@dataclass
class ScriptProfile:
    arabic: int = 0
    latin: int = 0
    other: int = 0
    other_samples: list[str] = field(default_factory=list)
    latin_text: str = ""

    @property
    def letters(self) -> int:
        return self.arabic + self.latin + self.other

    @property
    def classification(self) -> str:
        """'none' | 'arabic' | 'latin' | 'other' | 'mixed'"""
        if self.letters == 0:
            return "none"
        if self.is_foreign_script:
            return "other"
        if self.arabic and self.latin:
            return "mixed"
        if self.arabic:
            return "arabic"
        return "latin"

    @property
    def is_foreign_script(self) -> bool:
        if self.other == 0:
            return False
        if self.other >= 5:
            return True
        return self.other >= 2 and self.other / max(self.letters, 1) >= 0.10


def analyze(text: str) -> ScriptProfile:
    p = ScriptProfile()
    latin_tokens: list[str] = []
    for token in text.split():
        has_latin = False
        has_arabic = False
        for ch in token:
            sc = script_of(ch)
            if sc == "arabic":
                p.arabic += 1
                has_arabic = True
            elif sc == "latin":
                p.latin += 1
                has_latin = True
            elif sc == "other":
                p.other += 1
                if len(p.other_samples) < 6:
                    p.other_samples.append(ch)
        if has_latin and not has_arabic:
            latin_tokens.append(token)
    p.latin_text = " ".join(latin_tokens)
    return p


def latin_letter_count(text: str) -> int:
    return sum(1 for ch in text if script_of(ch) == "latin")
