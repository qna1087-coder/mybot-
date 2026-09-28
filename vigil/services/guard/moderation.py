"""English moderation through OpenRouter with a free-model fallback chain.

Facts that shape this client (OpenRouter, Sept 2026):
- every ``:free`` model is limited to 20 requests/min;
- the daily cap (50/day, 1000/day after a one-time $10 purchase) is per ACCOUNT, not per model;
  so the chain protects against outages and per-minute limits, not against the daily cap.
Hence: cache, local pre-filters, an explicit daily budget, and fail-open by default.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from vigil.core.errors import ModerationUnavailable
from vigil.db.repo import usage as usage_repo
from vigil.services.context import Services

log = logging.getLogger("vigil.moderation")

SYSTEM_PROMPT = """You are the content-safety classifier for a public Telegram channel. You receive one message written by a channel administrator. Decide whether it violates the channel policy.

Flag the message (flagged=true) if it contains, promotes, requests or sells any of the ENABLED categories:
{categories}

Category meanings:
- sexual: pornography, explicit sexual content or services, sexual solicitation
- minors: any sexualization or exploitation of children or teenagers (always highest severity)
- drugs: illegal drugs or controlled substances — use, sale, sourcing or glorification
- violence: graphic violence, gore, threats, incitement
- hate: hatred or dehumanization of protected groups
- harassment: targeted abuse, bullying, doxxing
- self_harm: encouragement or instructions for suicide or self-harm
- weapons: sale or manufacturing of weapons or explosives
- extremism: terrorist or violent-extremist propaganda or recruitment
- scam: fraud, phishing, fake giveaways, pump-and-dump, spam promotion
- other: anything else clearly inappropriate for a general audience

Do not flag ordinary news, opinion, humor, education, or medical/harm-reduction information. Be conservative with ambiguous text and firm with explicit text.

Also detect the primary language of the text as an ISO 639-1 code (e.g. "en", "fr", "tr").

Respond with ONLY a JSON object, no prose, no markdown:
{{"flagged": true|false, "category": "<one of the categories or none>", "severity": "low|medium|high", "language": "<iso-639-1>", "reason": "<at most 12 words>"}}"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class ModerationResult:
    flagged: bool
    category: str = "none"
    severity: str = "low"
    language: str = "en"
    reason: str = ""
    model: str = ""
    latency_ms: int = 0
    cached: bool = False
    raw: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["raw"] = (self.raw or "")[:300]
        return d


class ModerationClient:
    def __init__(self, ctx: Services):
        self.ctx = ctx
        cfg = ctx.config
        self.chain: list[str] = list(cfg.model_chain)
        self._http = httpx.AsyncClient(
            base_url=cfg.openrouter_base_url.rstrip("/"),
            timeout=httpx.Timeout(cfg.moderation_timeout_seconds, connect=min(5.0, cfg.moderation_timeout_seconds)),
            headers={
                "Authorization": f"Bearer {cfg.openrouter_api_key}",
                "HTTP-Referer": cfg.moderation_http_referer,
                "X-Title": cfg.moderation_app_title,
                "Content-Type": "application/json",
            },
        )
        self._cooldown_until: dict[str, float] = {}
        self._cache: dict[str, tuple[ModerationResult, float]] = {}
        self._budget_exhausted_day: str | None = None
        self._day_requests: dict[str, int] = {}
        self._last_error: str | None = None
        self._last_model: str | None = None
        self._lock = asyncio.Lock()

    # ── public ───────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self.ctx.config.moderation_enabled

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def budget_left(self) -> int:
        used = self._day_requests.get(self._today(), 0)
        return max(self.ctx.config.moderation_daily_budget - used, 0)

    async def classify(self, s: AsyncSession, text: str, enabled_categories: list[str]) -> ModerationResult:
        if not self.enabled:
            raise ModerationUnavailable("moderation disabled: no API key or model chain")
        normalized = " ".join(text.split())
        if not normalized:
            return ModerationResult(flagged=False, reason="empty")
        key = hashlib.sha256(f"{sorted(enabled_categories)}|{normalized.lower()}".encode()).hexdigest()
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and cached[1] > now:
            r = cached[0]
            return ModerationResult(**{**asdict(r), "cached": True})

        today = self._today()
        await self._load_usage(s, today)
        if self._day_requests.get(today, 0) >= self.ctx.config.moderation_daily_budget:
            self._budget_exhausted_day = today
            raise ModerationUnavailable("daily budget exhausted")

        result = await self._classify_with_chain(s, normalized, enabled_categories)
        self._cache[key] = (result, now + self.ctx.config.moderation_cache_ttl_seconds)
        if len(self._cache) > 5000:
            self._evict_cache()
        return result

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        today = self._today()
        return {
            "enabled": self.enabled,
            "chain": self.chain,
            "cooling": {m: int(t - now) for m, t in self._cooldown_until.items() if t > now},
            "requests_today": self._day_requests.get(today, 0),
            "budget": self.ctx.config.moderation_daily_budget,
            "budget_exhausted": self._budget_exhausted_day == today,
            "last_model": self._last_model,
            "last_error": self._last_error,
            "cache_size": len(self._cache),
            "fail_mode": self.ctx.config.moderation_fail_mode,
        }

    async def key_info(self) -> dict[str, Any] | None:
        """Best-effort GET /key — shows OpenRouter's own view of usage and limits."""
        if not self.enabled:
            return None
        try:
            r = await self._http.get("/key", timeout=6.0)
            if r.status_code == 200:
                return (r.json() or {}).get("data")
        except (httpx.HTTPError, ValueError):
            return None
        return None

    async def close(self) -> None:
        await self._http.aclose()

    # ── internals ────────────────────────────────────────────

    async def _load_usage(self, s: AsyncSession, today: str) -> None:
        if today in self._day_requests:
            return
        row = await usage_repo.get_day(s, today)
        self._day_requests = {today: row.requests if row else 0}

    def _evict_cache(self) -> None:
        now = time.monotonic()
        for k in [k for k, (_, exp) in self._cache.items() if exp <= now]:
            self._cache.pop(k, None)
        while len(self._cache) > 4000:
            self._cache.pop(next(iter(self._cache)))

    def _payload(self, model: str, text: str, categories: list[str], *, extras: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(categories=", ".join(categories))},
                {"role": "user", "content": f"MESSAGE:\n{text[:2000]}"},
            ],
            "temperature": 0,
            "max_tokens": 220,
        }
        if extras:
            body["response_format"] = {"type": "json_object"}
            effort = self.ctx.config.moderation_reasoning_effort
            if effort != "off":
                body["reasoning"] = {"effort": effort, "exclude": True}
        return body

    async def _classify_with_chain(self, s: AsyncSession, text: str, categories: list[str]) -> ModerationResult:
        today = self._today()
        errors: list[str] = []
        now = time.monotonic()
        for model in self.chain:
            if self._cooldown_until.get(model, 0) > now:
                continue
            for extras in (True, False):
                started = time.monotonic()
                try:
                    r = await self._http.post("/chat/completions", json=self._payload(model, text, categories, extras=extras))
                except httpx.TimeoutException:
                    errors.append(f"{model}: timeout")
                    self._cooldown_until[model] = time.monotonic() + 30
                    break
                except httpx.HTTPError as e:
                    errors.append(f"{model}: {type(e).__name__}")
                    self._cooldown_until[model] = time.monotonic() + 30
                    break

                latency = int((time.monotonic() - started) * 1000)
                if r.status_code == 200:
                    self._day_requests[today] = self._day_requests.get(today, 0) + 1
                    content, served_model = self._extract_content(r)
                    parsed = self._parse(content, categories)
                    if parsed is None:
                        errors.append(f"{model}: unparseable")
                        await usage_repo.bump(s, today, model=model, ok=False, error="unparseable")
                        break  # try next model, not the no-extras variant
                    parsed.model = served_model or model
                    parsed.latency_ms = latency
                    parsed.raw = content[:300]
                    self._last_model = parsed.model
                    self._last_error = None
                    await usage_repo.bump(s, today, model=parsed.model, ok=True)
                    return parsed

                detail = self._error_detail(r)
                if r.status_code == 429:
                    if "day" in detail.lower() or "daily" in detail.lower():
                        self._budget_exhausted_day = today
                        self._last_error = f"daily limit: {detail[:120]}"
                        raise ModerationUnavailable("openrouter daily free limit reached")
                    self._cooldown_until[model] = time.monotonic() + 65
                    errors.append(f"{model}: 429")
                    break
                if r.status_code in (401, 402, 403):
                    self._last_error = f"{r.status_code}: {detail[:120]}"
                    raise ModerationUnavailable(f"openrouter {r.status_code}: {detail[:120]}")
                if r.status_code == 404:
                    self._cooldown_until[model] = time.monotonic() + 6 * 3600
                    errors.append(f"{model}: 404")
                    break
                if r.status_code == 400 and extras and self._is_param_error(detail):
                    continue  # retry the same model without response_format / reasoning
                if r.status_code >= 500 or r.status_code == 408:
                    self._cooldown_until[model] = time.monotonic() + 45
                errors.append(f"{model}: {r.status_code}")
                break
        msg = "; ".join(errors[-4:]) or "no model available"
        self._last_error = msg
        await usage_repo.bump(s, today, model=None, ok=False, error=msg)
        raise ModerationUnavailable(msg)

    @staticmethod
    def _error_detail(r: httpx.Response) -> str:
        try:
            data = r.json()
            err = data.get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                return str(err.get("message") or err)
            return str(err or data)[:300]
        except ValueError:
            return r.text[:300]

    @staticmethod
    def _is_param_error(detail: str) -> bool:
        d = detail.lower()
        return any(k in d for k in ("response_format", "json_object", "reasoning", "not supported", "unsupported", "invalid parameter"))

    @staticmethod
    def _extract_content(r: httpx.Response) -> tuple[str, str]:
        try:
            data = r.json()
        except ValueError:
            return r.text, ""
        served = str(data.get("model") or "")
        choices = data.get("choices") or []
        if not choices:
            return "", served
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content or ""), served

    @staticmethod
    def _parse(content: str, enabled: list[str]) -> ModerationResult | None:
        if not content:
            return None
        text = content.strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
        obj: dict[str, Any] | None = None
        try:
            obj = json.loads(text)
        except ValueError:
            m = _JSON_RE.search(text)
            if m:
                candidate = m.group(0)
                for attempt in (candidate, candidate.rstrip("`").strip()):
                    try:
                        obj = json.loads(attempt)
                        break
                    except ValueError:
                        continue
        if not isinstance(obj, dict):
            low = text.lower()
            if low.startswith("unsafe"):
                cat = "other"
                m2 = re.search(r"unsafe\W+([a-z_ ,]+)", low)
                if m2:
                    cat = m2.group(1).split(",")[0].strip().replace(" ", "_") or "other"
                return ModerationResult(flagged=True, category=cat, severity="high", reason="unsafe")
            if low.startswith("safe"):
                return ModerationResult(flagged=False, reason="safe")
            return None
        flagged = obj.get("flagged")
        if flagged is None:
            flagged = obj.get("violation", obj.get("unsafe", False))
        if isinstance(flagged, str):
            flagged = flagged.strip().lower() in ("true", "yes", "1", "unsafe")
        category = str(obj.get("category") or "none").strip().lower().replace("-", "_").replace(" ", "_")
        if category in ("", "null", "safe"):
            category = "none"
        if bool(flagged) and category != "none" and category not in enabled:
            # The model flagged a category the channel does not enforce.
            flagged = False
        severity = str(obj.get("severity") or "medium").lower()
        if severity not in ("low", "medium", "high"):
            severity = "medium"
        language = str(obj.get("language") or "en").strip().lower()[:5] or "en"
        reason = str(obj.get("reason") or "")[:160]
        return ModerationResult(flagged=bool(flagged), category=category, severity=severity, language=language, reason=reason)
