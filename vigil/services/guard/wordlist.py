"""A small local fast path for unmistakable English terms. Saves API calls; the model remains
the real judge. Deliberately conservative: only terms that are explicit in any context."""

from __future__ import annotations

import re

from vigil.services.guard.verdict import KIND_CONTENT, Verdict

_PATTERNS: dict[str, list[str]] = {
    "sexual": [
        r"\bporn(?:o|ography|hub)?\b",
        r"\bxxx\b",
        r"\bnudes?\b",
        r"\bhentai\b",
        r"\bonlyfans\b",
        r"\bsex\s*(?:cam|chat|video|tape)s?\b",
        r"\bescorts?\b",
        r"\bcamgirls?\b",
    ],
    "drugs": [
        r"\bcocaine\b",
        r"\bheroin\b",
        r"\bmethamphetamine\b",
        r"\bcrystal\s*meth\b",
        r"\bfentanyl\b",
        r"\bmdma\b",
        r"\becstasy\s*pills?\b",
        r"\bweed\s*(?:for\s*sale|dealer|delivery)\b",
        r"\bbuy\s*(?:drugs|cocaine|weed|xanax|lsd)\b",
    ],
    "minors": [
        r"\bchild\s*porn\b",
        r"\bcp\s*(?:links?|videos?|content)\b",
        r"\bunderage\s*(?:girls?|boys?|sex|nudes?)\b",
        r"\bloli(?:con)?\b",
    ],
    "scam": [
        r"\bfree\s*(?:crypto|bitcoin|btc)\s*giveaway\b",
        r"\bdouble\s*your\s*(?:btc|bitcoin|money)\b",
        r"\bguaranteed\s*profit\b",
    ],
}

_COMPILED = [(cat, re.compile(p, re.IGNORECASE)) for cat, pats in _PATTERNS.items() for p in pats]


def check(latin_text: str, enabled_categories: set[str]) -> Verdict | None:
    if not latin_text:
        return None
    for category, rx in _COMPILED:
        if category not in enabled_categories:
            continue
        m = rx.search(latin_text)
        if m:
            return Verdict(
                kind=KIND_CONTENT,
                rule=f"wordlist:{category}",
                detail=m.group(0)[:60],
                severity="high",
                api_result={"source": "local_wordlist", "category": category, "match": m.group(0)[:60]},
            )
    return None
