from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Violation kinds — one vocabulary shared by guards, enforcement, notifications and the audit log.
KIND_LINK = "link"
KIND_MENTION = "mention"
KIND_FORWARD = "forward"
KIND_MEDIA = "media"
KIND_EMOJI = "emoji"
KIND_LANGUAGE = "language"
KIND_LENGTH = "length"
KIND_CONTENT = "content"


@dataclass
class Verdict:
    kind: str
    rule: str
    detail: str = ""
    severity: str = "medium"  # low | medium | high
    excerpt: str | None = None
    api_result: dict[str, Any] | None = None
    related_message_ids: list[int] = field(default_factory=list)

    @property
    def is_length(self) -> bool:
        return self.kind == KIND_LENGTH
