"""Benchmark Vigil's real GuardPipeline on a synthetic corpus of channel posts.

Measures: per-post decision latency of the local layers, which layer caught what,
and how many posts needed the external moderation API (stubbed, counted, not called).
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN-NOT-REAL-XXXXXXXXXXXXXXXX")
os.environ.setdefault("SYSTEM_OWNER_ID", "100")
os.environ.setdefault("OPENROUTER_API_KEY", "")

from tests.conftest import CHANNEL_ID, FakeBot, make_post, photo  # noqa: E402
from vigil.app import build_services  # noqa: E402
from vigil.config import Settings  # noqa: E402
from vigil.db.engine import Database  # noqa: E402
from vigil.db.models import Channel  # noqa: E402
from vigil.services.guard.moderation import ModerationResult  # noqa: E402
from vigil.services.settings import DEFAULTS, ChannelSettings  # noqa: E402

AR = [
    "صباح الخير متابعينا الكرام، إليكم أهم أخبار اليوم",
    "تم تحديث جدول الدوام الرسمي ابتداءً من الأسبوع القادم",
    "شكو ماكو اليوم؟ نزلنا تقرير جديد عن الأسعار",
    "تنبيه: البث المباشر سيبدأ الساعة التاسعة مساءً",
    "نتائج المسابقة ستعلن غدًا إن شاء الله",
]
MIXED = [
    "اليوم نتحدث عن Machine Learning و Python",
    "إصدار جديد من iOS متوفر الآن",
    "مباراة Real Madrid الليلة الساعة العاشرة",
]
EN_OK = ["Good morning everyone", "New update is live now", "Match starts at 9pm tonight"]
EN_BAD_WORDLIST = ["buy cocaine here cheap", "send nudes now"]


def corpus(n: int, seed: int = 7):
    rnd = random.Random(seed)
    kinds = (
        ["arabic"] * 46 + ["mixed"] * 14 + ["en_ok"] * 6 + ["link"] * 8 + ["mention"] * 5
        + ["forward"] * 4 + ["photo_ok"] * 6 + ["video"] * 4 + ["foreign"] * 3 + ["long_en"] * 3 + ["wordlist"] * 1
    )
    for i in range(n):
        k = rnd.choice(kinds)
        mid = i + 1
        if k == "arabic":
            yield k, make_post(mid, text=rnd.choice(AR))
        elif k == "mixed":
            yield k, make_post(mid, text=rnd.choice(MIXED))
        elif k == "en_ok":
            yield k, make_post(mid, text=rnd.choice(EN_OK))
        elif k == "link":
            t = "تابعونا على https://t.me/other"
            yield k, make_post(mid, text=t, entities=[{"type": "url", "offset": 11, "length": 19}])
        elif k == "mention":
            t = "تواصلوا مع @someone"
            yield k, make_post(mid, text=t, entities=[{"type": "mention", "offset": 11, "length": 8}])
        elif k == "forward":
            yield k, make_post(mid, text=rnd.choice(AR), forward_origin={"type": "hidden_user", "date": 0, "sender_user_name": "X"})
        elif k == "photo_ok":
            yield k, make_post(mid, caption=rnd.choice(AR), photo=photo())
        elif k == "video":
            yield k, make_post(mid, caption="فيديو", video={"file_id": "v", "file_unique_id": "vu", "width": 1, "height": 1, "duration": 3})
        elif k == "foreign":
            yield k, make_post(mid, text="Привет всем, как дела")
        elif k == "long_en":
            yield k, make_post(mid, text="This is a very long English announcement " * 3)
        else:
            yield k, make_post(mid, text=rnd.choice(EN_BAD_WORDLIST))


async def main(n: int = 1000):
    tmp = tempfile.mkdtemp()
    cfg = Settings(bot_token=os.environ["BOT_TOKEN"], system_owner_id=100, openrouter_api_key="",
                   database_url=f"sqlite+aiosqlite:///{tmp}/b.db", default_timezone="UTC")
    db = Database(cfg.database_url)
    await db.init()
    ctx = build_services(cfg, db, FakeBot())  # type: ignore[arg-type]

    api_calls = 0

    async def fake_classify(s, text, cats):
        nonlocal api_calls
        api_calls += 1
        return ModerationResult(flagged=False, language="en")

    ctx.moderation.classify = fake_classify  # type: ignore[method-assign]
    settings = ChannelSettings(json.loads(json.dumps(DEFAULTS)))
    ch = Channel(id=CHANNEL_ID, title="Bench")
    posts = list(corpus(n))

    lat: list[float] = []
    by_layer: dict[str, int] = {}
    async with db.session() as s:
        for _ in range(50):  # warm-up
            await ctx.guard.evaluate(s, ch, posts[0][1], settings)
        api_calls = 0
        for kind, msg in posts:
            before = api_calls
            t0 = time.perf_counter()
            v = await ctx.guard.evaluate(s, ch, msg, settings)
            dt = (time.perf_counter() - t0) * 1000
            if api_calls == before:
                lat.append(dt)
            layer = v.rule.split(":")[0] if v else "clean"
            by_layer[layer] = by_layer.get(layer, 0) + 1

    lat.sort()
    out = {
        "posts": n,
        "api_calls": api_calls,
        "local_decision_pct": round(100 * (n - api_calls) / n, 1),
        "local_latency_ms": {
            "median": round(statistics.median(lat), 3),
            "p95": round(lat[int(len(lat) * 0.95)], 3),
            "p99": round(lat[int(len(lat) * 0.99)], 3),
        },
        "by_layer": dict(sorted(by_layer.items(), key=lambda kv: -kv[1])),
        "violations": n - by_layer.get("clean", 0),
    }
    await ctx.moderation.close()
    await db.dispose()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000))
