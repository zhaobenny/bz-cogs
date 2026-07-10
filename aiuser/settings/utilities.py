from __future__ import annotations

import asyncio
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Tuple

import discord
from redbot.core import commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from aiuser.types.enums import MentionType
from aiuser.utils.prompt_metrics import (
    get_prompt_metrics_for_context,
)

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices


async def confirm_pending(
    ctx: commands.Context, embed: discord.Embed, timeout: float = 30.0
) -> Tuple[bool, discord.Message]:
    """Ask a yes/no reaction confirmation.

    Returns ``(confirmed, prompt_message)``. On timeout or "no" the prompt is
    edited to "Cancelled." and ``confirmed`` is False; on "yes" the caller is
    expected to edit the returned message with the outcome.
    """
    confirm = await ctx.send(embed=embed)
    start_adding_reactions(confirm, ReactionPredicate.YES_OR_NO_EMOJIS)
    pred = ReactionPredicate.yes_or_no(confirm, ctx.author)
    try:
        await ctx.bot.wait_for("reaction_add", timeout=timeout, check=pred)
    except asyncio.TimeoutError:
        pred.result = False

    if pred.result is not True:
        await confirm.edit(
            embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color())
        )
        return False, confirm
    return True, confirm


def get_mention_type(mention) -> MentionType:
    if isinstance(mention, discord.Member):
        return MentionType.USER
    elif isinstance(mention, discord.Role):
        return MentionType.ROLE
    elif isinstance(
        mention,
        (
            discord.TextChannel,
            discord.VoiceChannel,
            discord.StageChannel,
            discord.ForumChannel,
        ),
    ):
        return MentionType.CHANNEL
    else:
        return MentionType.SERVER


def get_config_attribute(
    config, mention_type: MentionType, ctx: commands.Context, mention
):
    if mention_type == MentionType.SERVER:
        return config.guild(ctx.guild)
    elif mention_type == MentionType.USER:
        return config.member(mention)
    elif mention_type == MentionType.ROLE:
        return config.role(mention)
    elif mention_type == MentionType.CHANNEL:
        return config.channel(mention)


async def add_prompt_metrics_fields(
    embed: discord.Embed,
    services: AIUserServices,
    ctx: commands.Context,
    prompt: str,
) -> None:
    metrics = await get_prompt_metrics_for_context(ctx, services, prompt)
    embed.add_field(name="Tokens", value=metrics.token_label)
    if metrics.cost_per_1k_label:
        embed.add_field(
            name="Estimated Cost / 1K uses",
            value=metrics.cost_per_1k_label,
        )


def truncate_prompt(prompt: str, limit: int = 1900) -> str:
    if len(prompt) > limit:
        return prompt[:limit] + "..."
    return prompt


def rank_choices_for_query(choices: list, query: str) -> list:
    query = (query or "").casefold().strip()
    if not query:
        return choices

    query_parts = [part for part in query.replace("/", " ").replace("-", " ").split()]

    def score(choice: str) -> tuple:
        normalized = choice.casefold()
        parts = normalized.replace("/", " ").replace("-", " ").split()
        ratio = SequenceMatcher(None, query, normalized).ratio()
        windows = (
            normalized[index : index + len(query)]
            for index in range(max(len(normalized) - len(query) + 1, 1))
        )
        partial_ratio = max(
            (SequenceMatcher(None, query, window).ratio() for window in windows),
            default=0,
        )
        token_hits = sum(
            1 for query_part in query_parts if any(query_part in part for part in parts)
        )
        startswith = normalized.startswith(query)
        contains = query in normalized
        return (startswith, contains, token_hits, partial_ratio, ratio)

    return sorted(choices, key=score, reverse=True)
