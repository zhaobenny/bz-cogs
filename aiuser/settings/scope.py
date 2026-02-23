from __future__ import annotations

from typing import Optional, Tuple

import discord
from redbot.core import commands

from aiuser.core.hierarchy import get_highest_configured_role_config_value
from aiuser.settings.utilities import get_config_attribute, get_mention_type
from aiuser.types.abc import MixinMeta
from aiuser.types.enums import MentionType
from aiuser.types.types import COMPATIBLE_MENTIONS

SCOPED_TARGET_TYPES = (
    discord.Member,
    discord.Role,
    discord.TextChannel,
    discord.VoiceChannel,
    discord.StageChannel,
    discord.ForumChannel,
)


def get_settings_target_scope(
    cog: MixinMeta,
    ctx: commands.Context,
    mention: Optional[COMPATIBLE_MENTIONS],
) -> Tuple[MentionType, object]:
    mention_type = get_mention_type(mention)
    return mention_type, get_config_attribute(cog.config, mention_type, ctx, mention)


def parse_target_or_value(first, second):
    if isinstance(first, SCOPED_TARGET_TYPES):
        return first, second
    return None, first


def parse_target_or_text(first, rest: Optional[str]):
    if isinstance(first, SCOPED_TARGET_TYPES):
        return first, (rest or "").strip()

    if rest:
        return None, f"{first} {rest}".strip()
    return None, str(first).strip()


async def get_broader_scoped_setting_for_target(
    cog: MixinMeta,
    ctx: commands.Context,
    mention: Optional[COMPATIBLE_MENTIONS],
    attr_name: str,
):
    """Get the inherited value a scoped settings target would fall back to."""
    mention_type = get_mention_type(mention)

    if mention_type == MentionType.SERVER:
        return await getattr(cog.config.guild(ctx.guild), attr_name)()

    if mention_type == MentionType.USER and isinstance(mention, discord.Member):
        role_value = await get_highest_configured_role_config_value(
            cog, mention, attr_name
        )
        if role_value is not None:
            return role_value

    if mention_type != MentionType.CHANNEL:
        channel_value = await getattr(cog.config.channel(ctx.channel), attr_name)()
        if channel_value is not None:
            return channel_value

    return await getattr(cog.config.guild(ctx.guild), attr_name)()


async def get_effective_scoped_setting_for_target(
    cog: MixinMeta,
    ctx: commands.Context,
    mention: Optional[COMPATIBLE_MENTIONS],
    attr_name: str,
):
    mention_type, config_attr = get_settings_target_scope(cog, ctx, mention)
    current = await getattr(config_attr, attr_name)()
    if current is not None or mention_type == MentionType.SERVER:
        return current
    return await get_broader_scoped_setting_for_target(cog, ctx, mention, attr_name)
