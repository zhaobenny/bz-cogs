from __future__ import annotations

from typing import Any, Optional

import discord

from aiuser.types.abc import MixinMeta


async def get_highest_configured_role_config_value(
    cog: MixinMeta,
    member: discord.Member,
    attr_name: str,
) -> Any:
    """Return the highest configured role override for a member, if any."""

    try:
        configured_role_ids = set(await cog.config.all_roles())
    except Exception:
        return None

    roles = sorted(
        member.roles,
        key=lambda role: (getattr(role, "position", 0), role.id),
        reverse=True,
    )
    for role in roles:
        if role.id not in configured_role_ids:
            continue
        try:
            value = await getattr(cog.config.role(role), attr_name)()
        except Exception:
            continue
        if value is not None:
            return value

    return None


async def get_hierarchical_config_value(
    cog: MixinMeta,
    *,
    guild: discord.Guild,
    channel: discord.abc.GuildChannel,
    author: Optional[discord.abc.User],
    attr_name: str,
) -> Any:
    """Resolve a config attribute using member > role > channel > guild precedence.

    `None` means "not set at this level" and falls back to broader scopes.
    Falsy values like `0`, `False`, and `[]` are treated as explicit overrides.
    """

    role_value = None
    if isinstance(author, discord.Member):
        role_value = await get_highest_configured_role_config_value(
            cog, author, attr_name
        )

    try:
        if author is not None:
            value = await getattr(cog.config.member(author), attr_name)()
            if value is not None:
                return value
    except Exception:
        pass

    if role_value is not None:
        return role_value

    channel_value = await getattr(cog.config.channel(channel), attr_name)()
    if channel_value is not None:
        return channel_value

    return await getattr(cog.config.guild(guild), attr_name)()


async def get_ctx_hierarchical_config_value(
    cog: MixinMeta,
    ctx,
    attr_name: str,
) -> Any:
    return await get_hierarchical_config_value(
        cog,
        guild=ctx.guild,
        channel=ctx.channel,
        author=getattr(ctx, "author", None),
        attr_name=attr_name,
    )


async def get_message_hierarchical_config_value(
    cog: MixinMeta,
    message: discord.Message,
    attr_name: str,
) -> Any:
    return await get_hierarchical_config_value(
        cog,
        guild=message.guild,
        channel=message.channel,
        author=message.author,
        attr_name=attr_name,
    )
