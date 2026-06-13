from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from aiuser.config.models import (
    OTHER_MODELS_LIMITS,
    TOOLS_SUPPORTED_MODELS,
    UNSUPPORTED_LOGIT_BIAS_MODELS,
    VISION_SUPPORTED_MODELS,
)

DEFAULT_TOKEN_LIMIT = 7000


@dataclass(frozen=True)
class ModelInfo:
    """Capability flags and limits for a model name.

    The generated tables in :mod:`aiuser.config.models` are matched by
    substring; this is the only place in the codebase that may do so.
    """

    name: str
    supports_vision: bool
    supports_tools: bool
    supports_logit_bias: bool
    token_limit: int


def _matches_any(model: str, candidates: Iterable[str]) -> bool:
    return any(candidate in model for candidate in candidates)


def get_token_limit(model: str) -> int:
    """Best-effort prompt token limit for a model name (conservative default)."""
    limit = DEFAULT_TOKEN_LIMIT

    if "gemini-2" in model or "gemini-3" in model:
        limit = 940000
    if "gpt-4.1" in model:
        limit = 942818
    if "gpt-5" in model:
        limit = 115200

    if "100k" in model:
        limit = 98000
    if "16k" in model:
        limit = 15000
    if "32k" in model:
        limit = 31000

    matching_keys = [key for key in OTHER_MODELS_LIMITS if key in model]
    if matching_keys:
        best_match = max(matching_keys, key=len)
        limit = OTHER_MODELS_LIMITS[best_match]

    return limit


def get_model_info(model: str) -> ModelInfo:
    model = model or ""
    return ModelInfo(
        name=model,
        supports_vision=_matches_any(model, VISION_SUPPORTED_MODELS),
        supports_tools=_matches_any(model, TOOLS_SUPPORTED_MODELS),
        # vision-tuned chat models commonly reject logit_bias as well, so both
        # lists disqualify it (matches long-standing behaviour)
        supports_logit_bias=not _matches_any(
            model, VISION_SUPPORTED_MODELS + UNSUPPORTED_LOGIT_BIAS_MODELS
        ),
        token_limit=get_token_limit(model),
    )
