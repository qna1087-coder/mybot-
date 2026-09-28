"""Application configuration.

Every secret comes from the environment (or a local .env file that is never committed).
Nothing here has a hard-coded token, key or ID.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MODELS = (
    "nvidia/nemotron-3-ultra-550b-a55b:free,"
    "qwen/qwen3.8-27b:free,"
    "nvidia/nemotron-3-super-120b-a12b:free,"
    "google/gemma-4-31b-it:free,"
    "nvidia/nemotron-3.5-lightning:free,"
    "inclusionai/ling-3.0-flash-fin:free,"
    "openrouter/free"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Telegram ──────────────────────────────────────────────
    bot_token: str = Field(..., min_length=20)
    system_owner_id: int

    # ── Moderation API (OpenRouter) ───────────────────────────
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    moderation_models: str = DEFAULT_MODELS
    moderation_timeout_seconds: float = 12.0
    moderation_fail_mode: Literal["open", "closed"] = "open"
    moderation_daily_budget: int = 45
    moderation_cache_ttl_seconds: int = 86_400
    moderation_reasoning_effort: Literal["low", "medium", "high", "off"] = "low"
    moderation_http_referer: str = "https://github.com/vigil-bot"
    moderation_app_title: str = "Vigil Protection System"

    # ── Storage ───────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/vigil.db"

    # ── Defaults ──────────────────────────────────────────────
    default_timezone: str = "Asia/Baghdad"
    default_language: Literal["en", "ar"] = "en"
    unauthorized_notice_in_channel: bool = True

    # ── Runtime ───────────────────────────────────────────────
    shield_tick_seconds: int = 30
    admin_sync_minutes: int = 15
    media_group_window_seconds: float = 2.5
    log_level: str = "INFO"

    # ── Webhook (optional) ────────────────────────────────────
    webhook_url: str = ""
    webhook_path: str = "/telegram/webhook"
    webhook_secret: str = ""
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    @field_validator("moderation_models")
    @classmethod
    def _strip_models(cls, v: str) -> str:
        return ",".join(m.strip() for m in v.split(",") if m.strip())

    @property
    def model_chain(self) -> list[str]:
        return [m for m in self.moderation_models.split(",") if m]

    @property
    def moderation_enabled(self) -> bool:
        return bool(self.openrouter_api_key) and bool(self.model_chain)

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
