from __future__ import annotations

import json

import httpx
import pytest

from vigil.core.errors import ModerationUnavailable
from vigil.services.guard.moderation import ModerationClient


def _client(ctx, handler):
    ctx.config.openrouter_api_key = "sk-test"
    ctx.config.moderation_models = "a/one:free,b/two:free,openrouter/free"
    mc = ModerationClient(ctx)
    mc._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://example.invalid/api/v1")
    return mc


def _ok(model: str, content: str) -> httpx.Response:
    return httpx.Response(200, json={"model": model, "choices": [{"message": {"content": content}}]})


def test_parse_variants():
    p = ModerationClient._parse
    assert p('{"flagged": true, "category": "drugs", "severity": "high", "language": "en"}', ["drugs"]).flagged
    r = p('```json\n{"flagged": false, "category": "none", "language": "fr"}\n```', ["drugs"])
    assert not r.flagged and r.language == "fr"
    r = p('<think>hmm</think>\nSure! {"flagged": "yes", "category": "sexual"}', ["sexual"])
    assert r.flagged and r.category == "sexual"
    # category not enforced by the channel → not flagged
    assert not p('{"flagged": true, "category": "violence"}', ["drugs"]).flagged
    assert p("unsafe\nS3, S5", ["other"]).flagged
    assert not p("safe", ["other"]).flagged
    assert p("garbage", ["other"]) is None


async def test_fallback_chain_and_cooldown(ctx):
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        calls.append(body["model"])
        if body["model"] == "a/one:free":
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return _ok(body["model"], '{"flagged": true, "category": "drugs", "severity": "high", "language": "en", "reason": "sale"}')

    mc = _client(ctx, handler)
    async with ctx.db.session() as s:
        r = await mc.classify(s, "buy stuff", ["drugs"])
    assert r.flagged and r.model == "b/two:free"
    assert calls == ["a/one:free", "b/two:free"]
    assert "a/one:free" in mc.status()["cooling"]
    # second call: cached, no HTTP
    async with ctx.db.session() as s:
        r2 = await mc.classify(s, "buy  stuff ", ["drugs"])
    assert r2.cached and len(calls) == 2
    await mc.close()


async def test_param_error_retries_without_extras(ctx):
    seen: list[bool] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append("response_format" in body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": {"message": "response_format is not supported"}})
        return _ok(body["model"], '{"flagged": false, "category": "none", "language": "en"}')

    mc = _client(ctx, handler)
    async with ctx.db.session() as s:
        r = await mc.classify(s, "hello there", ["drugs"])
    assert not r.flagged and seen == [True, False]
    await mc.close()


async def test_all_models_down_raises_and_budget(ctx):
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "down"}})

    mc = _client(ctx, handler)
    async with ctx.db.session() as s:
        with pytest.raises(ModerationUnavailable):
            await mc.classify(s, "hello there", ["drugs"])
    st = mc.status()
    assert st["last_error"]
    # daily budget guard
    ctx.config.moderation_daily_budget = 0
    mc2 = _client(ctx, handler)
    async with ctx.db.session() as s:
        with pytest.raises(ModerationUnavailable, match="budget"):
            await mc2.classify(s, "another text", ["drugs"])
    await mc.close()
    await mc2.close()
