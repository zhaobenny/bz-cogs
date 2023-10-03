import asyncio
import logging
from typing import Optional, Union

import discord
import tiktoken
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import SimpleMenu, start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from aiuser.abc import MixinMeta, aiuser
from aiuser.prompts.common.presets import DEFAULT_PROMPT, PRESETS

logger = logging.getLogger("red.bz_cogs.aiuser")


class PromptSettings(MixinMeta):

    @aiuser.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def prompt(self, _):
        """ Change the prompt settings for the current server

            (All subcommands are per server)
        """
        pass

    @prompt.command(name="reset")
    async def prompt_reset(self, ctx: commands.Context):
        """ Reset ALL prompts in this guild to default (inc. channels and members) """
        embed = discord.Embed(
            title="Are you sure?",
            description="This will reset *ALL* prompts in this guild to default (including per channels and per member)",
            color=await ctx.embed_color())
        confirm = await ctx.send(embed=embed)
        start_adding_reactions(confirm, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(confirm, ctx.author)
        try:
            await ctx.bot.wait_for("reaction_add", timeout=10.0, check=pred)
        except asyncio.TimeoutError:
            return await confirm.edit(embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color()))
        if pred.result is False:
            return await confirm.edit(embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color()))
        else:
            self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
            await self.config.guild(ctx.guild).custom_text_prompt.set(None)
            for member in ctx.guild.members:
                await self.config.member(member).custom_text_prompt.set(None)
            for channel in ctx.guild.channels:
                await self.config.channel(channel).custom_text_prompt.set(None)
            return await confirm.edit(embed=discord.Embed(title="All prompts have been reset to default.", color=await ctx.embed_color()))

    @prompt.group(name="show", invoke_without_command=True)
    async def prompt_show(self, ctx, mention: Optional[Union[discord.Member, discord.TextChannel]]):
        """ Show the prompt for the server (or provided mention)
            **Arguments**
                - `mention` *(Optional)* Mention of user or channel
        """
        if mention and isinstance(mention, discord.Member):
            prompt = await self.config.member(mention).custom_text_prompt()
            title = f"The prompt for this user ({mention.display_name}) is:"
        elif mention and isinstance(mention, discord.TextChannel):
            prompt = await self.config.channel(mention).custom_text_prompt()
            title = f"The prompt for this channel ({mention.name}) is:"
        else:
            channel_prompt = await self.config.channel(ctx.channel).custom_text_prompt()
            prompt = channel_prompt or await self.config.guild(ctx.guild).custom_text_prompt() or DEFAULT_PROMPT
            title = f"The prompt for this {'channel' if channel_prompt else 'server'} is:"

        embed = discord.Embed(
            title=title,
            description=self._truncate_prompt(prompt),
            color=await ctx.embed_color()
        )
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        await ctx.send(embed=embed)

    @prompt_show.command(name="server", aliases=["guild"])
    async def show_server_prompt(self, ctx: commands.Context):
        """ Show the current server prompt """
        prompt = await self.config.guild(ctx.guild).custom_text_prompt() or DEFAULT_PROMPT
        embed = discord.Embed(
            title=f"The prompt for this server is:",
            description=self._truncate_prompt(prompt),
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        await ctx.send(embed=embed)

    @prompt_show.command(name="members", aliases=["users"])
    async def show_user_prompts(self, ctx: commands.Context):
        """ Show all users with custom prompts """
        pages = []
        for member in ctx.guild.members:
            prompt = await self.config.member(member).custom_text_prompt()
            if prompt:
                page = discord.Embed(
                    title=f"The prompt for user {member.display_name} is:",
                    description=self._truncate_prompt(prompt),
                    color=await ctx.embed_color())
                page.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
                pages.append(page)
        if not pages:
            return await ctx.send("No users with custom prompts")
        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")
        await SimpleMenu(pages).start(ctx)

    @prompt_show.command(name="channels")
    async def show_channel_prompts(self, ctx: commands.Context):
        """ Show all channels with custom prompts """
        pages = []
        for channel in ctx.guild.channels:
            prompt = await self.config.channel(channel).custom_text_prompt()
            if prompt:
                page = discord.Embed(
                    title=f"The prompt for channel #{channel.name} is:",
                    description=self._truncate_prompt(prompt),
                    color=await ctx.embed_color())
                page.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
                pages.append(page)
        if not pages:
            return await ctx.send("No channels with custom prompts")
        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")
        await SimpleMenu(pages).start(ctx)

    @prompt.command(name="preset")
    async def prompt_preset(self, ctx: commands.Context, *, preset: str):
        """ Set/list preset prompts

            Use [p]aiuser prompt preset list to see available presets.

            **Arguments**
                - `preset` The preset to use
        """
        if preset == 'list':
            embed = discord.Embed(
                title="Presets",
                description=f"Use `{ctx.clean_prefix}aiuser prompt preset <preset>` to set a preset.",
                color=await ctx.embed_color())
            embed.add_field(name="Available presets",
                            value="\n".join(PRESETS.keys()), inline=False)
            return await ctx.send(embed=embed)
        if preset not in PRESETS:
            return await ctx.send("Invalid preset. Use `list` to see available presets.")
        await self.config.guild(ctx.guild).custom_text_prompt.set(PRESETS[preset])
        embed = discord.Embed(
            title="The prompt for this server is now changed to:",
            description=f"{self._truncate_prompt(PRESETS[preset])}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, PRESETS[preset]))
        return await ctx.send(embed=embed)

    @prompt.command(name="set", aliases=["custom", "customize"])
    async def prompt_custom(self, ctx, mention: Optional[Union[discord.Member, discord.TextChannel]], *, prompt: Optional[str]):
        """ Set a custom prompt for the server (or provided mention)

            **Arguments**
                - `mention` *(Optional)* Mention of a specific user or channel
        """
        if not prompt:
            prompt = None
        if prompt and len(prompt) > await self.config.max_prompt_length() and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f"Prompt too long. Max length is {await self.config.max_prompt_length()} characters.")
        if isinstance(mention, discord.Member):
            await self.set_user_prompt(ctx, mention, prompt)
        elif isinstance(mention, discord.TextChannel):
            await self.set_channel_prompt(ctx, mention, prompt)
        else:
            await self.set_server_prompt(ctx, prompt)

    async def set_server_prompt(self, ctx: commands.Context, prompt: Optional[str]):
        """ Set custom prompt for current server """
        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        if not prompt:
            await self.config.guild(ctx.guild).custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for this server is now reset to the default prompt")
        await self.config.guild(ctx.guild).custom_text_prompt.set(prompt)
        embed = discord.Embed(
            title="The prompt for this server is now changed to:",
            description=f"{self._truncate_prompt(prompt)}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        return await ctx.send(embed=embed)

    async def set_user_prompt(self, ctx: commands.Context, member: discord.Member, prompt: Optional[str]):
        """ Set custom prompt for a member of this server, overrides server and channel prompts """
        if not prompt:
            await self.config.member(member).custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for user {member.display_name} is now reset to default server prompt.")
        await self.config.member(member).custom_text_prompt.set(prompt)
        embed = discord.Embed(
            title=f"The prompt for user {member.display_name} is now changed to:",
            description=f"{self._truncate_prompt(prompt)}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        return await ctx.send(embed=embed)

    async def set_channel_prompt(self, ctx: commands.Context, mention: discord.TextChannel, prompt: Optional[str]):
        """ Set custom prompt for the current channel, overrides the server prompt """
        channel = mention or ctx.channel
        if not prompt:
            await self.config.channel(channel).custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for {channel.mention} is now reset to default server prompt.")
        await self.config.channel(channel).custom_text_prompt.set(prompt)
        embed = discord.Embed(
            title=f"The prompt for channel #{ctx.channel.name} is now changed to:",
            description=f"{self._truncate_prompt(prompt)}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        return await ctx.send(embed=embed)

    @prompt.group(name="topics")
    async def random_topics(self, _):
        """ Manage topics to be used in random messages for current server (if enabled for server by bot owner) """
        pass

    @random_topics.command(name="show", aliases=["list"])
    async def show_random_topics(self, ctx: commands.Context):
        """ Lists topics to used in random messages """
        topics = await self.config.guild(ctx.guild).random_messages_topics()

        if not topics:
            return await ctx.send("The topic list is empty.")

        formatted_list = "\n".join(f"{index+1}. {topic}" for index, topic in enumerate(topics))
        pages = []
        for text in pagify(formatted_list, page_length=888):
            page = discord.Embed(
                title=f"List of random message topics in {ctx.guild.name}",
                description=box(text),
                color=await ctx.embed_color())
            pages.append(page)

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")

        return await SimpleMenu(pages).start(ctx)

    @random_topics.command(name="add", aliases=["a"])
    async def add_random_topics(self, ctx: commands.Context, *, topic: str):
        """ Add a new topic """
        topics = await self.config.guild(ctx.guild).random_messages_topics()
        if topic in topics:
            return await ctx.send("That topic is already in the list.")
        if topic and len(topic) > await self.config.max_topic_length() and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f"Topic too long. Max length is {await self.config.max_topic_length()} characters.")
        topics.append(topic)
        await self.config.guild(ctx.guild).random_messages_topics.set(topics)
        embed = discord.Embed(
            title="Added topic to random message topics:",
            description=f"{topic}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, topic))
        return await ctx.send(embed=embed)

    @random_topics.command(name="remove", aliases=["rm", "delete"])
    async def remove_random_topics(self, ctx: commands.Context, *, number: int):
        """ Removes a topic (by number) from the list"""
        topics = await self.config.guild(ctx.guild).random_messages_topics()
        if not (1 <= number <= len(topics)):
            return await ctx.send("Invalid topic number.")
        topic = topics[number - 1]
        topics.remove(topic)
        await self.config.guild(ctx.guild).random_messages_topics.set(topics)
        embed = discord.Embed(
            title="Removed topic from random message topics:",
            description=f"{topic}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    async def get_tokens(self, ctx: commands.Context, prompt: str) -> int:
        prompt = f"You are {ctx.guild.me.nick or ctx.guild.me.name}. {prompt}"
        try:
            encoding = tiktoken.encoding_for_model(await self.config.guild(ctx.guild).model())
        except KeyError:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(prompt, disallowed_special=()))

    @staticmethod
    def _truncate_prompt(prompt: str) -> str:
        return prompt[:1900] + "..." if len(prompt) > 1900 else prompt
