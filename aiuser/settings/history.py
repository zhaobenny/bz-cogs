import logging
from typing import Optional

import discord
from redbot.core import checks, commands

from aiuser.types.abc import MixinMeta, aiuser

logger = logging.getLogger("red.bz_cogs.aiuser")


class HistorySettings(MixinMeta):
    @aiuser.group(name="history", aliases=["context"])
    @checks.is_owner()
    async def history(self, _):
        """Change the prompt context settings for the current server

        The most recent messages that are within the time gap and message limits are used to create context.
        Context is used to help the LLM generate a response.
        """
        pass

    @history.command(name="backread", aliases=["messages", "size"])
    async def history_backread(self, ctx: commands.Context, new_value: int):
        """Set max amount of messages to be used as context

        (Increasing the number of messages will increase the cost of the response, messages will be added until the LLM's token limit is reached)
        """
        await self.config.guild(ctx.guild).messages_backread.set(new_value)
        embed = discord.Embed(
            title="The number of previous messages used for context on this server is now:",
            description=f"{new_value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @history.command(name="customtokenlimit")
    async def history_maxtokens(self, ctx: commands.Context, new_value: Optional[int]):
        """
        Set a LLM's custom maximum context limit (for local LLMs or those not listed in `aiuser/common/constants.py`.).

        If not set, a safe default or saved limit from `aiuser/common/constants.py` is used.
        """
        await self.config.guild(ctx.guild).custom_model_tokens_limit.set(new_value)
        embed = discord.Embed(
            title="The custom token limit for this server is now:",
            description=f"{new_value} \n\n-# The limit may need changing for different models.",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @history.command(name="time", aliases=["gap"])
    async def history_time(self, ctx: commands.Context, new_value: int):
        """Set max time (sec) messages can be apart before no more can be added

        eg. if set to 60, once messsages are more than 60 seconds apart, more messages will not be added.

        Helpful to prevent the LLM from mixing up context from different conversations.
        """
        await self.config.guild(ctx.guild).messages_backread_seconds.set(new_value)
        embed = discord.Embed(
            title="The max time (s) allowed between messages for context on this server is now:",
            description=f"{new_value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)
