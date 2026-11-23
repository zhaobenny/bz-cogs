from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger("red.bz_cogs.aiuser")

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
MODELS_CACHE_FILENAME = "models_cache.json"
MODELS_CACHE_TTL_SECONDS = 48 * 60 * 60
DEFAULT_TOKEN_LIMIT = 15000
EXCLUDED_MODEL_ALIASES = frozenset({"auto", "free"})
UNSUPPORTED_LOGIT_BIAS_MODELS = ("o3-mini", "o3-mini-2025-01-31")


@dataclass(frozen=True)
class ModelInfo:
    """Capability flags, token limit, and prompt price for a model name."""

    name: str
    supports_vision: bool
    supports_tools: bool
    supports_logit_bias: bool
    token_limit: int
    prompt_price: Decimal | None = None


@dataclass
class _CatalogState:
    models: dict[str, dict[str, Any]] = field(default_factory=dict)
    data_path: Path | None = None
    fetched_at: float = 0.0
    next_retry_at: float = 0.0
    refresh_task: asyncio.Task[bool] | None = None

    def is_fresh(self) -> bool:
        return (
            self.fetched_at > 0
            and (time.time() - self.fetched_at) < MODELS_CACHE_TTL_SECONDS
        )


_state = _CatalogState()


def _normalize_model_name(model: str) -> str:
    return (model or "").strip().rsplit("/", 1)[-1].split(":", 1)[0].lower()


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True,
)
async def _fetch_openrouter_models() -> Any:
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:  # noqa: SIM117 - Keep context managers on separate lines for Python 3.9.
        async with session.get(OPENROUTER_MODELS_URL) as response:
            response.raise_for_status()
            return await response.json()


def load_model_catalog_cache(data_path: Path) -> bool:
    """Load cached model metadata from disk.

    Returns True when the cache exists and is still within its TTL. Stale
    caches are still loaded into memory so lookups work while a refresh runs.
    """
    _state.data_path = data_path
    cache_path = data_path / MODELS_CACHE_FILENAME
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _state.fetched_at = 0.0
        return False

    if not isinstance(raw, dict) or not isinstance(raw.get("models"), dict):
        _state.fetched_at = 0.0
        return False

    models = raw["models"]
    if not all(isinstance(k, str) and isinstance(v, dict) for k, v in models.items()):
        _state.fetched_at = 0.0
        return False

    _state.models = models
    fetched_at = raw.get("fetched_at")
    _state.fetched_at = (
        float(fetched_at) if isinstance(fetched_at, (int, float)) else 0.0
    )
    return _state.is_fresh()


async def refresh_model_catalog(data_path: Path, *, force: bool = False) -> bool:
    """Fetch OpenRouter's public model catalog and persist it to disk."""
    _state.data_path = data_path
    if not force and load_model_catalog_cache(data_path):
        return False

    _state.next_retry_at = time.time() + 15 * 60 + random.uniform(0, 5)
    try:
        payload = await _fetch_openrouter_models()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        logger.warning("Failed to refresh OpenRouter model catalog: %s", exc)
        return False

    models_data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(models_data, list):
        logger.warning("Unexpected OpenRouter model catalog payload")
        return False

    catalog: dict[str, dict[str, Any]] = {}
    for model in models_data:
        if not isinstance(model, dict):
            continue
        model_id = model.get("id")
        if not isinstance(model_id, str):
            continue
        base_name = _normalize_model_name(model_id)
        if not base_name or base_name in EXCLUDED_MODEL_ALIASES:
            continue

        entry = catalog.setdefault(
            base_name,
            {
                "vision": False,
                "tools": False,
                "token_limit": None,
                "prompt_price": None,
            },
        )

        arch = model.get("architecture")
        modalities = arch.get("input_modalities") if isinstance(arch, dict) else None
        if isinstance(modalities, list) and "image" in modalities:
            entry["vision"] = True

        params = model.get("supported_parameters")
        if isinstance(params, list) and "tools" in params:
            entry["tools"] = True

        context_length = model.get("context_length")
        if isinstance(context_length, (int, float)) and context_length > 0:
            safe_limit = int(context_length * 0.9)
            if entry["token_limit"] is None or safe_limit > entry["token_limit"]:
                entry["token_limit"] = safe_limit

        pricing = model.get("pricing")
        price = (
            _parse_decimal(pricing.get("prompt")) if isinstance(pricing, dict) else None
        )
        if price is not None and price >= 0:
            prev = _parse_decimal(entry["prompt_price"])
            if prev is None or price < prev:
                entry["prompt_price"] = str(price)

    fetched_at = time.time()
    _state.models = catalog
    _state.fetched_at = fetched_at

    try:
        cache_path = data_path / MODELS_CACHE_FILENAME
        tmp_path = cache_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps({"fetched_at": fetched_at, "models": catalog}),
            encoding="utf-8",
        )
        os.replace(tmp_path, cache_path)
    except OSError as exc:
        logger.warning("Failed to save OpenRouter model catalog cache: %s", exc)

    logger.debug("Refreshed OpenRouter model catalog (%d models)", len(catalog))
    return True


def schedule_model_catalog_refresh() -> None:
    """Trigger a background refresh if the cache is missing or past its TTL."""
    if _state.data_path is None or _state.is_fresh():
        return
    if _state.refresh_task is not None and not _state.refresh_task.done():
        return
    if time.time() < _state.next_retry_at:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _state.refresh_task = loop.create_task(refresh_model_catalog(_state.data_path))


def cancel_model_catalog_refresh() -> None:
    """Cancel any in-flight background catalog refresh."""
    if _state.refresh_task is not None and not _state.refresh_task.done():
        _state.refresh_task.cancel()
    _state.refresh_task = None
    _state.next_retry_at = 0.0


def get_model_info(model: str) -> ModelInfo:
    model = model or ""
    base_name = _normalize_model_name(model)

    entry = _state.models.get(base_name)
    if entry is None and base_name:
        matches = [key for key in _state.models if base_name.startswith(f"{key}-")]
        if matches:
            matched_key = max(matches, key=len)
            entry = _state.models[matched_key]
            logger.debug("Matched model %r to %r (%s)", model, matched_key, entry)
    entry = entry or {}

    supports_vision = bool(entry.get("vision", False))
    supports_tools = bool(entry.get("tools", False))
    raw_limit = entry.get("token_limit")
    token_limit = (
        raw_limit
        if isinstance(raw_limit, int)
        and not isinstance(raw_limit, bool)
        and raw_limit > 0
        else DEFAULT_TOKEN_LIMIT
    )
    prompt_price = _parse_decimal(entry.get("prompt_price"))

    # vision-tuned chat models commonly reject logit_bias as well
    supports_logit_bias = not supports_vision and not any(
        base_name == m or base_name.startswith(f"{m}-")
        for m in UNSUPPORTED_LOGIT_BIAS_MODELS
    )

    schedule_model_catalog_refresh()
    return ModelInfo(
        name=model,
        supports_vision=supports_vision,
        supports_tools=supports_tools,
        supports_logit_bias=supports_logit_bias,
        token_limit=token_limit,
        prompt_price=prompt_price,
    )
