from __future__ import annotations

import asyncio
from typing import Tuple

import discord
from redbot.core import Config, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from aiuser.types.enums import MentionType
from aiuser.utils.prompt_metrics import (
    get_prompt_metrics_for_context,
)


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
    config: Config,
    ctx: commands.Context,
    prompt: str,
) -> None:
    metrics = await get_prompt_metrics_for_context(ctx, config, prompt)
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
