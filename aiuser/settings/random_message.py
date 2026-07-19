import logging

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import SimpleMenu

from aiuser.settings.utilities import add_prompt_metrics_fields
from aiuser.settings._groups import aiuser
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


class RandomMessageSettings(MixinMeta):
    @aiuser.group(name="random", aliases=["randommessage"])
    @checks.admin_or_permissions(manage_guild=True)
    async def randommessage(self, _):
        """Configure messages sent without an immediate user trigger"""
        pass

    @randommessage.command(name="show")
    async def random_show(self, ctx: commands.Context):
        """Show random message settings"""
        guild_conf = self.config.guild(ctx.guild)
        prompts = await guild_conf.random_messages_prompts()
        embed = discord.Embed(
            title="Random message settings", color=await ctx.embed_color()
        )
        embed.add_field(
            name="Enabled",
            value="Yes" if await guild_conf.random_messages_enabled() else "No",
        )
        embed.add_field(
            name="Chance",
            value=f"`{await guild_conf.random_messages_percent() * 100:.2f}%`",
        )
        embed.add_field(name="Prompts", value=f"`{len(prompts)}`")
        return await ctx.send(embed=embed)

    @randommessage.command(name="enable")
    @checks.is_owner()
    async def random_enable(self, ctx: commands.Context):
        """Enable random messages"""
        await self.config.guild(ctx.guild).random_messages_enabled.set(True)
        return await ctx.send("Random messages enabled.")

    @randommessage.command(name="disable")
    @checks.is_owner()
    async def random_disable(self, ctx: commands.Context):
        """Disable random messages"""
        await self.config.guild(ctx.guild).random_messages_enabled.set(False)
        return await ctx.send("Random messages disabled.")

    @randommessage.group(
        name="chance", aliases=["percent"], invoke_without_command=True
    )
    async def random_chance(self, ctx: commands.Context):
        """Show the random message chance"""
        percent = await self.config.guild(ctx.guild).random_messages_percent()
        return await ctx.maybe_send_embed(
            f"Random message chance: `{percent * 100:.2f}%`"
        )

    @random_chance.command(name="set")
    async def set_random_rng(self, ctx: commands.Context, percent: float):
        """Set the chance of sending a random message"""
        if percent < 0 or percent > 100:
            return await ctx.send("Please enter a number between 0 and 100.")
        await self.config.guild(ctx.guild).random_messages_percent.set(percent / 100)
        return await ctx.send(f"Random message chance set to `{percent:.2f}%`.")

    @randommessage.group(
        name="prompts", aliases=["topics"], invoke_without_command=True
    )
    async def random_prompts(self, ctx: commands.Context):
        """List prompts used to start random messages"""
        prompts = await self.config.guild(ctx.guild).random_messages_prompts()

        if not prompts:
            return await ctx.send("The prompt list is empty.")

        formatted_list = "\n".join(
            f"{index + 1}. {prompt}" for index, prompt in enumerate(prompts)
        )
        pages = []
        for text in pagify(formatted_list, page_length=888):
            page = discord.Embed(
                title=f"List of random message prompt in {ctx.guild.name}",
                description=box(text),
                color=await ctx.embed_color(),
            )
            pages.append(page)

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i + 1} of {len(pages)}")

        return await SimpleMenu(pages).start(ctx)

    @random_prompts.command(name="add", aliases=["a"])
    async def add_random_prompts(self, ctx: commands.Context, *, prompt: str):
        """Add a new prompt to be used in random messages"""
        prompts = await self.config.guild(ctx.guild).random_messages_prompts()
        if prompt in prompts:
            return await ctx.send("That prompt is already in the list.")
        if (
            prompt
            and len(prompt) > await self.config.max_random_prompt_length()
            and not await ctx.bot.is_owner(ctx.author)
        ):
            return await ctx.send(
                f"Topic too long. Max length is {await self.config.max_random_prompt_length()} characters."
            )
        prompts.append(prompt)
        await self.config.guild(ctx.guild).random_messages_prompts.set(prompts)
        embed = discord.Embed(
            title="Added topic to random message prompts:",
            description=f"{prompt}",
            color=await ctx.embed_color(),
        )
        await add_prompt_metrics_fields(embed, self.services, ctx, prompt)
        return await ctx.send(embed=embed)

    @random_prompts.command(name="remove", aliases=["rm", "delete"])
    async def remove_random_prompts(self, ctx: commands.Context, *, number: int):
        """Removes a prompt (by number) from the list"""
        prompts = await self.config.guild(ctx.guild).random_messages_prompts()
        if not (1 <= number <= len(prompts)):
            return await ctx.send("Invalid topic number.")
        prompt = prompts[number - 1]
        prompts.remove(prompt)
        await self.config.guild(ctx.guild).random_messages_prompts.set(prompts)
        embed = discord.Embed(
            title="Removed topic from random message prompts:",
            description=f"{prompt}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @random_prompts.command(name="clear")
    async def clear_random_prompts(self, ctx: commands.Context):
        """Clear the random message prompt list"""
        await self.config.guild(ctx.guild).random_messages_prompts.set([])
        return await ctx.send("Random prompt list cleared.")
