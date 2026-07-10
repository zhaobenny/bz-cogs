from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from aiuser.config.models import OPENROUTER_MODEL_PROMPT_PRICES
from aiuser.utils.utilities import (
    encode_text_to_tokens,
    format_variables,
    get_tokenizer_encoding,
)

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices


@dataclass
class PromptMetrics:
    tokens: int
    token_label: str
    cost_per_1k_label: str | None
    tokenizer_name: str
    uses_fallback_tokenizer: bool


def format_tokens(tokens: int) -> str:
    return f"{tokens:,} token" if tokens == 1 else f"{tokens:,} tokens"


def format_cost(cost: Decimal) -> str:
    if cost == 0:
        return "$0"
    if cost < Decimal("0.01"):
        return "< $0.01"
    return f"${cost:.6f}".rstrip("0").rstrip(".")


def get_prompt_token_price(model: str) -> Decimal | None:
    base_name = model.rsplit("/", 1)[-1].split(":", 1)[0]
    price = OPENROUTER_MODEL_PROMPT_PRICES.get(base_name)
    if price is None:
        return None
    return Decimal(price)


def get_tokenizer_status(model: str) -> tuple[str, bool]:
    _, tokenizer_name, is_fallback = get_tokenizer_encoding(model)
    return tokenizer_name, is_fallback


async def get_prompt_metrics(text: str, model: str) -> PromptMetrics:
    tokens = await encode_text_to_tokens(text, model)
    prompt_token_price = get_prompt_token_price(model)
    tokenizer_name, uses_fallback_tokenizer = get_tokenizer_status(model)
    cost_per_1k_label = None
    if prompt_token_price is not None:
        cost_per_1k_label = format_cost(prompt_token_price * tokens * 1000)

    return PromptMetrics(
        tokens=tokens,
        token_label=format_tokens(tokens),
        cost_per_1k_label=cost_per_1k_label,
        tokenizer_name=tokenizer_name,
        uses_fallback_tokenizer=uses_fallback_tokenizer,
    )


async def get_prompt_metrics_for_context(
    ctx, services: AIUserServices, text: str
) -> PromptMetrics:
    model = await services.config.guild(ctx.guild).model()
    formatted = await format_variables(ctx, text, services) if text else text
    return await get_prompt_metrics(formatted, model)
