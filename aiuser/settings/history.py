import logging
import discord
from redbot.core import checks, commands

from aiuser.settings._groups import aiuser
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


class HistorySettings(MixinMeta):
    @aiuser.group(name="context", aliases=["history"])
    @checks.is_owner()
    async def history(self, _):
        """Configure conversation context"""
        pass

    @history.group(
        name="messages", aliases=["backread", "size"], invoke_without_command=True
    )
    async def history_backread(self, ctx: commands.Context):
        """Show the maximum messages used as context"""
        value = await self.config.guild(ctx.guild).messages_backread()
        return await ctx.maybe_send_embed(f"Context message limit: `{value}`")

    @history_backread.command(name="set")
    async def history_backread_set(self, ctx: commands.Context, messages: int):
        """Set the maximum messages used as context"""
        if messages < 0:
            return await ctx.send("Please enter a non-negative number.")
        await self.config.guild(ctx.guild).messages_backread.set(messages)
        return await ctx.send(f"Context message limit set to `{messages}`.")

    @history.group(
        name="token_limit", aliases=["customtokenlimit"], invoke_without_command=True
    )
    async def history_maxtokens(self, ctx: commands.Context):
        """Show the custom context token limit"""
        value = await self.config.guild(ctx.guild).custom_model_tokens_limit()
        return await ctx.maybe_send_embed(
            f"Custom context token limit: `{value or 'Automatic'}`"
        )

    @history_maxtokens.command(name="set")
    async def history_maxtokens_set(self, ctx: commands.Context, tokens: int):
        """Set a custom context token limit"""
        if tokens < 1:
            return await ctx.send("Please enter a positive number.")
        await self.config.guild(ctx.guild).custom_model_tokens_limit.set(tokens)
        return await ctx.send(f"Custom context token limit set to `{tokens}`.")

    @history_maxtokens.command(name="clear")
    async def history_maxtokens_clear(self, ctx: commands.Context):
        """Use the automatically detected context token limit"""
        await self.config.guild(ctx.guild).custom_model_tokens_limit.set(None)
        return await ctx.send("Custom context token limit cleared.")

    @history.group(name="gap", aliases=["time"], invoke_without_command=True)
    async def history_time(self, ctx: commands.Context):
        """Show the maximum gap between context messages"""
        seconds = await self.config.guild(ctx.guild).messages_backread_seconds()
        return await ctx.maybe_send_embed(
            f"Maximum context message gap: `{seconds}` seconds"
        )

    @history_time.command(name="set")
    async def history_time_set(self, ctx: commands.Context, seconds: int):
        """Set the maximum gap between context messages"""
        if seconds < 0:
            return await ctx.send("Please enter a non-negative number.")
        await self.config.guild(ctx.guild).messages_backread_seconds.set(seconds)
        return await ctx.send(
            f"Maximum context message gap set to `{seconds}` seconds."
        )

    @history.group(name="compaction", aliases=["compact"])
    async def history_compaction(self, ctx: commands.Context):
        """Settings for dynamically squashing older messages to save tokens"""
        pass

    @history_compaction.command(name="show")
    async def history_compaction_show(self, ctx: commands.Context):
        """Show whether context compaction is enabled"""
        enabled = await self.config.guild(ctx.guild).compaction_enabled()
        return await ctx.maybe_send_embed(f"Context compaction enabled: `{enabled}`")

    @history_compaction.command(name="enable")
    async def history_compaction_enable(self, ctx: commands.Context):
        """Enable context compaction"""
        await self.config.guild(ctx.guild).compaction_enabled.set(True)
        return await ctx.send("Context compaction enabled.")

    @history_compaction.command(name="disable")
    async def history_compaction_disable(self, ctx: commands.Context):
        """Disable context compaction"""
        await self.config.guild(ctx.guild).compaction_enabled.set(False)
        return await ctx.send("Context compaction disabled.")

    @history_compaction.group(name="prompt", invoke_without_command=True)
    async def history_compaction_prompt(self, ctx: commands.Context):
        """Show the custom context compaction prompt"""
        prompt = await self.config.guild(ctx.guild).custom_compaction_prompt()
        embed = discord.Embed(
            title="Context compaction prompt",
            description=prompt or "Default",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @history_compaction_prompt.command(name="set")
    async def history_compaction_prompt_set(
        self, ctx: commands.Context, *, prompt: str
    ):
        """Set a custom prompt used to summarize context"""
        await self.config.guild(ctx.guild).custom_compaction_prompt.set(prompt)
        embed = discord.Embed(
            title="Custom compaction prompt set",
            description=prompt[:2000],
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @history_compaction_prompt.command(name="clear")
    async def history_compaction_prompt_clear(self, ctx: commands.Context):
        """Use the default context compaction prompt"""
        await self.config.guild(ctx.guild).custom_compaction_prompt.set(None)
        return await ctx.send("Context compaction prompt reset to default.")
