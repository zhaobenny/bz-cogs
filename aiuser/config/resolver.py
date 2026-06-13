from __future__ import annotations

import logging
from typing import Any, Optional

import discord
from redbot.core import Config, commands

logger = logging.getLogger("red.bz_cogs.aiuser")


class ScopedConfigResolver:
    """The single source of truth for scoped setting resolution.

    Precedence: member > role > channel > guild.

    - `None` at a scope means "not set here", and resolution falls through to
      the next broader scope.
    - Falsy values like ``0``, ``False`` and ``[]`` are explicit overrides and
      stop the fallback.
    - When a member has several roles with a configured override, the
      highest-positioned role wins.
    - Member/role scopes only apply to real :class:`discord.Member` objects;
      webhook/user authors skip straight to the channel scope.
    """

    def __init__(self, config: Config):
        self.config = config

    async def get_role_override(
        self, member: discord.Member, attr_name: str
    ) -> Optional[Any]:
        """Return the highest-positioned configured role override, if any."""
        configured_role_ids = set(await self.config.all_roles())
        if not configured_role_ids:
            return None

        roles = sorted(
            member.roles,
            key=lambda role: (getattr(role, "position", 0), role.id),
            reverse=True,
        )
        for role in roles:
            if role.id not in configured_role_ids:
                continue
            value = await getattr(self.config.role(role), attr_name)()
            if value is not None:
                return value
        return None

    async def resolve(
        self,
        attr_name: str,
        *,
        guild: discord.Guild,
        channel: Optional[discord.abc.GuildChannel] = None,
        member: Optional[discord.abc.User] = None,
    ) -> Any:
        if isinstance(member, discord.Member):
            member_value = await getattr(self.config.member(member), attr_name)()
            if member_value is not None:
                return member_value

            role_value = await self.get_role_override(member, attr_name)
            if role_value is not None:
                return role_value

        if channel is not None:
            channel_value = await getattr(self.config.channel(channel), attr_name)()
            if channel_value is not None:
                return channel_value

        return await getattr(self.config.guild(guild), attr_name)()

    async def resolve_for_ctx(self, attr_name: str, ctx: commands.Context) -> Any:
        return await self.resolve(
            attr_name,
            guild=ctx.guild,
            channel=ctx.channel,
            member=getattr(ctx, "author", None),
        )

    async def resolve_for_message(self, attr_name: str, message: discord.Message) -> Any:
        return await self.resolve(
            attr_name,
            guild=message.guild,
            channel=message.channel,
            member=message.author,
        )
