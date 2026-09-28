#!/usr/bin/env python3
"""List OpenRouter's current free models and print a ready-to-paste MODERATION_MODELS line.

Usage:  python scripts/free_models.py [--json]
No API key needed. Pure standard library.
"""

from __future__ import annotations

import json
import sys
import urllib.request

URL = "https://openrouter.ai/api/v1/models"

# Models we prefer at the front of the chain when they are still free (smartest first).
PREFERRED = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "qwen/qwen3.8-27b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "inclusionai/ling-3.0-flash-fin:free",
]
EXCLUDE_HINTS = ("lyria", "vision-only", "content-safety", "audio", "music", "image")


def main() -> int:
    with urllib.request.urlopen(URL, timeout=20) as r:  # noqa: S310
        data = json.load(r)
    models = data.get("data", [])
    free = []
    for m in models:
        pricing = m.get("pricing") or {}
        if str(pricing.get("prompt", "1")) == "0" and str(pricing.get("completion", "1")) == "0":
            mods = (m.get("architecture") or {}).get("output_modalities") or ["text"]
            if "text" not in mods:
                continue
            free.append(m)
    free.sort(key=lambda m: (-int(m.get("context_length") or 0), m["id"]))
    if "--json" in sys.argv:
        print(json.dumps([{"id": m["id"], "name": m.get("name"), "context": m.get("context_length")} for m in free], indent=2))
        return 0
    print(f"{len(free)} free text models on OpenRouter\n")
    for m in free:
        print(f"  {m['id']:<55} ctx={m.get('context_length')}")
    ids = {m["id"] for m in free}
    chain = [p for p in PREFERRED if p in ids]
    for m in free:
        mid = m["id"]
        if mid in chain or mid == "openrouter/free" or any(h in mid for h in EXCLUDE_HINTS):
            continue
        if len(chain) >= 8:
            break
        chain.append(mid)
    if "openrouter/free" in ids:
        chain.append("openrouter/free")
    print("\nSuggested .env line:\n")
    print("MODERATION_MODELS=" + ",".join(chain))
    return 0


if __name__ == "__main__":
    sys.exit(main())
