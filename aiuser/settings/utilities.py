from __future__ import annotations

import discord
from redbot.core import Config, commands

from aiuser.types.enums import MentionType
from aiuser.utils.prompt_metrics import (
    get_prompt_metrics_for_context,
)


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
