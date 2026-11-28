from __future__ import annotations

from typing import ClassVar

from aiuser.config.constants import (
    DEFAULT_OPENROUTER_DECISION_MODEL,
    OPENROUTER_DECISIONS_URL,
)
from aiuser.providers.decision.noul import NoulDecisionProvider


class OpenRouterDecisionProvider(NoulDecisionProvider):
    """OpenRouter Decisions API (`POST /api/alpha/decisions`, e.g. TypeSafe Jev)."""

    name = "openrouter"
    default_model = DEFAULT_OPENROUTER_DECISION_MODEL
    default_endpoint = OPENROUTER_DECISIONS_URL
    extra_headers: ClassVar[dict[str, str]] = {
        "HTTP-Referer": "https://aiuser.zhao.gg",
        "X-OpenRouter-Title": "aiuser",
    }
