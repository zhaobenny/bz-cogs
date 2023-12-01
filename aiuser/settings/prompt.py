import asyncio
import json
import logging
from typing import Optional, Union

import discord
import tiktoken
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu, start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from aiuser.abc import MixinMeta, aiuser
from aiuser.common.constants import DEFAULT_PROMPT
from aiuser.common.utilities import format_variables

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
            description="This will reset *ALL* prompts in this guild to default (including per channel, per role and per member)",
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
            for role in ctx.guild.roles:
                await self.config.role(role).custom_text_prompt.set(None)
            return await confirm.edit(embed=discord.Embed(title="All prompts have been reset to default.", color=await ctx.embed_color()))

    @prompt.group(name="show", invoke_without_command=True)
    async def prompt_show(self, ctx: commands.Context, mention: Optional[Union[discord.Member, discord.Role, discord.TextChannel, discord.VoiceChannel, discord.StageChannel]]):
        """ Show the prompt for the server (or provided user/channel)
            **Arguments**
                - `mention` *(Optional)* User or channel
        """
        if mention and isinstance(mention, discord.Member):
            prompt = await self.config.member(mention).custom_text_prompt()
            title = f"The prompt for the user {mention.display_name} is:"
        elif mention and isinstance(mention, discord.Role):
            prompt = await self.config.role(mention).custom_text_prompt()
            title = f"The prompt for the role {mention.name} is:"
        elif mention and isinstance(mention, discord.TextChannel) or isinstance(mention, discord.VoiceChannel) or isinstance(mention, discord.StageChannel):
            prompt = await self.config.channel(mention).custom_text_prompt()
            title = f"The prompt for {mention.mention} is:"
        else:
            channel_prompt = await self.config.channel(ctx.channel).custom_text_prompt()
            prompt = channel_prompt or await self.config.guild(ctx.guild).custom_text_prompt()
            title = f"The prompt for {ctx.channel.mention if channel_prompt else 'this server'} is:"

        if not prompt:
            prompt = DEFAULT_PROMPT

        embed = discord.Embed(
            title=title,
            description=self._truncate_prompt(prompt),
            color=await ctx.embed_color()
        )
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        await ctx.send(embed=embed)

    @prompt_show.command(name="members", aliases=["users"])
    async def show_user_prompts(self, ctx: commands.Context):
        """ Show all users with custom prompts """
        await self._show_prompts(ctx, ctx.guild.members, "user")

    @prompt_show.command(name="roles")
    async def show_role_prompts(self, ctx: commands.Context):
        """ Show all roles with custom prompts """
        await self._show_prompts(ctx, ctx.guild.roles, "role")

    @prompt_show.command(name="channels")
    async def show_channel_prompts(self, ctx: commands.Context):
        """ Show all channels with custom prompts """
        await self._show_prompts(ctx, ctx.guild.channels, "channel")

    async def _get_custom_prompt(self, ctx, entity, entity_name, entity_type):

        if entity_type == "user":
            custom_prompt = await self.config.member(entity).custom_text_prompt()
        elif entity_type == "role":
            custom_prompt = await self.config.role(entity).custom_text_prompt()
        elif entity_type == "channel":
            custom_prompt = await self.config.channel(entity).custom_text_prompt()

        if not custom_prompt:
            return None

        embed = discord.Embed(
            title=f"The prompt for {entity_type} {entity_name} is:",
            description=self._truncate_prompt(custom_prompt),
            color=await ctx.embed_color()
        )
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, custom_prompt))
        return embed

    async def _show_prompts(self, ctx, entities, entity_type):
        pages = []
        for entity in entities:
            entity_name = entity.display_name if entity_type == "user" else entity.name
            embed = await self._get_custom_prompt(ctx, entity, entity_name, entity_type)
            if embed:
                pages.append(embed)

        if not pages:
            return await ctx.send(f"No {entity_type}s with custom prompts")

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")

        await SimpleMenu(pages).start(ctx)

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

    @prompt.group(name="preset")
    async def prompt_preset(self, _: commands.Context):
        """ Manage presets for the current server
        """
        pass

    @prompt_preset.command(name="show", aliases=["list"])
    async def show_presets(self, ctx: commands.Context):
        """ Show all presets for the current server """
        presets = json.loads(await self.config.guild(ctx.guild).presets())
        if not presets:
            return await ctx.send("No presets set for this server")
        pages = []
        for preset, prompt in presets.items():
            page = discord.Embed(
                title=f"Preset `{preset}`",
                description=self._truncate_prompt(prompt),
                color=await ctx.embed_color())
            page.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
            pages.append(page)
        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")
        await SimpleMenu(pages).start(ctx)

    @prompt_preset.command(name="add", aliases=["a"])
    async def add_preset(self, ctx: commands.Context, prompt: str):
        """ Add a new preset to the presets list

            **Arguments**
                - `prompt` The prompt to set. Use `|` to separate the preset name from the prompt at the start. eg. `preset_name|prompt_text`
        """
        presets = json.loads(await self.config.guild(ctx.guild).presets())
        split = prompt.split("|", 1)
        if not len(split) == 2:
            return await ctx.send("Invalid format. Use `|` to separate the preset name from the prompt at the start. eg. `preset_name|prompt text`")
        preset, prompt = split
        for channel in ctx.guild.channels:
            if channel.name.lower() == preset.lower():
                return await ctx.send(f"Cannot use `{preset}` as a preset name as it conflicts with the channel name <#{channel.id}>")
        if preset in presets:
            return await ctx.send("That preset name already exists.")
        if len(prompt) > await self.config.max_prompt_length() and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f"Prompt too long. Max length is {await self.config.max_prompt_length()} characters.")
        presets[preset] = prompt
        await self.config.guild(ctx.guild).presets.set(json.dumps(presets))
        embed = discord.Embed(
            title=f"Added preset `{preset}`",
            description=self._truncate_prompt(prompt),
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        return await ctx.send(embed=embed)

    @prompt_preset.command(name="remove", aliases=["rm", "delete"])
    async def remove_preset(self, ctx: commands.Context, preset: str):
        """
            Remove a preset by its name from the presets list

            **Arguments**
                - `preset` The name of the preset to remove
        """
        presets = json.loads(await self.config.guild(ctx.guild).presets())
        if preset not in presets:
            return await ctx.send("That preset name does not exist.")
        if preset == "cynical":
            return await ctx.send("Cannot remove the default preset.")
        prompt = presets.pop(preset)
        await self.config.guild(ctx.guild).presets.set(json.dumps(presets))
        embed = discord.Embed(
            title=f"Removed preset `{preset}`",
            description=self._truncate_prompt(prompt),
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @prompt.command(name="set", aliases=["custom", "customize"])
    async def prompt_custom(self, ctx, mention: Optional[Union[discord.Member, discord.Role, discord.TextChannel, discord.VoiceChannel, discord.StageChannel]], *, prompt: Optional[str]):
        """ Set a custom prompt or preset for the server (or provided channel/role/member)

            If multiple prompts can be used, the most specific prompt will be used, eg. it will go for: member > role > channel > server

            **Arguments**
                - `mention` *(Optional)* A specific user or channel
                - `prompt` *(Optional)* The prompt (or name of a preset) to set. If blank, will remove current prompt.
        """
        if not prompt:
            prompt = None
        if prompt and len(prompt) > await self.config.max_prompt_length() and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f"Prompt too long. Max length is {await self.config.max_prompt_length()} characters.")
        presets = json.loads(await self.config.guild(ctx.guild).presets())
        if prompt and prompt in presets:
            prompt = presets[prompt]

        entity_type = "server"
        if isinstance(mention, discord.Role):
            entity_type = "role"
        elif isinstance(mention, discord.Member):
            entity_type = "user"
        elif isinstance(mention, discord.TextChannel) or isinstance(mention, discord.VoiceChannel) or isinstance(mention, discord.StageChannel):
            entity_type = "channel"

        return await self._set_prompt(ctx, mention, entity_type, prompt)

    async def _set_prompt(self, ctx: commands.Context, entity, entity_type, prompt: Optional[str]):
        """ Set custom prompt for the specified entity type (server, channel, role, user) """

        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        config_attr = None

        if entity_type == "server":
            config_attr = self.config.guild(ctx.guild)
        elif entity_type == "user":
            config_attr = self.config.member(entity)
        elif entity_type == "role":
            config_attr = self.config.role(entity)
        elif entity_type == "channel":
            config_attr = self.config.channel(entity)

        if not config_attr:
            return await ctx.send("Invalid entity type provided.")

        if not prompt:
            await config_attr.custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for this {entity_type} is now reset to the default prompt")

        await config_attr.custom_text_prompt.set(prompt)
        embed = discord.Embed(
            title=f"The prompt for this {entity_type} is now changed to:",
            description=f"{self._truncate_prompt(prompt)}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        return await ctx.send(embed=embed)

    async def get_tokens(self, ctx: commands.Context, prompt: str) -> int:
        prompt = format_variables(ctx, prompt)  # to provide a better estimate
        try:
            encoding = tiktoken.encoding_for_model(await self.config.guild(ctx.guild).model())
        except KeyError:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(prompt, disallowed_special=()))

    @staticmethod
    def _truncate_prompt(prompt: str) -> str:
        return prompt[:1900] + "..." if len(prompt) > 1900 else prompt
