"""The 75-letter rule: too much English is deleted outright and never sent for analysis."""

from __future__ import annotations

from vigil.services.guard.language import latin_letter_count
from vigil.services.guard.verdict import KIND_LENGTH, Verdict


def check(text: str, limit: int) -> Verdict | None:
    if limit <= 0:
        return None
    count = latin_letter_count(text)
    if count > limit:
        return Verdict(
            kind=KIND_LENGTH,
            rule="length_guard:latin_letters",
            detail=f"{count}/{limit}",
            severity="low",
        )
    return None
