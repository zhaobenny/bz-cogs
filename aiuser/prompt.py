import asyncio
import json
import logging
from typing import Optional

import discord
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu, start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from aiuser.config.defaults import DEFAULT_PROMPT
from aiuser.settings.utilities import (
    get_config_attribute,
    get_mention_type,
    get_tokens,
    truncate_prompt,
)
from aiuser.types.abc import MixinMeta, aiuser
from aiuser.types.enums import MentionType
from aiuser.types.types import COMPATIBLE_MENTIONS

logger = logging.getLogger("red.bz_cogs.aiuser")


class PromptSettings(MixinMeta):

    @aiuser.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def prompt(self, ctx):
        """Change the prompt settings for the current server"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use a subcommand: `show`, `preset`, `set`, `reset`, `blacklist`.")

    # -------------------- RESET --------------------

    @prompt.command(name="reset")
    async def prompt_reset(self, ctx: commands.Context):
        """Reset ALL prompts in this guild to default"""
        embed = discord.Embed(
            title="Are you sure?",
            description="This will reset *ALL* prompts in this guild to default (including per channel, per role and per member)",
            color=await ctx.embed_color()
        )
        confirm = await ctx.send(embed=embed)
        start_adding_reactions(confirm, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(confirm, ctx.author)
        try:
            await ctx.bot.wait_for("reaction_add", timeout=10.0, check=pred)
        except asyncio.TimeoutError:
            return await confirm.edit(embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color()))
        if pred.result is False:
            return await confirm.edit(embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color()))
        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        await self.config.guild(ctx.guild).custom_text_prompt.set(None)
        for member in ctx.guild.members:
            await self.config.member(member).custom_text_prompt.set(None)
        for channel in ctx.guild.channels:
            await self.config.channel(channel).custom_text_prompt.set(None)
        for role in ctx.guild.roles:
            await self.config.role(role).custom_text_prompt.set(None)
        return await confirm.edit(embed=discord.Embed(title="All prompts have been reset to default.", color=await ctx.embed_color()))

    # -------------------- SHOW --------------------

    @prompt.group(name="show", invoke_without_command=True)
    async def prompt_show(self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS]):
        """Show the prompt for the server (or provided user/channel)"""
        if mention:
            mention_type = get_mention_type(mention)
            config_attr = get_config_attribute(self.config, mention_type, ctx, mention)
            prompt = await config_attr.custom_text_prompt()
            title = await self._get_embed_title(mention_type, mention)
        else:
            channel_prompt = await self.config.channel(ctx.channel).custom_text_prompt()
            prompt = channel_prompt or await self.config.guild(ctx.guild).custom_text_prompt() or DEFAULT_PROMPT
            title = f"The prompt for {ctx.channel.mention if channel_prompt else 'this server'} is:"

        if mention and not prompt:
            embed = discord.Embed(
                title=title,
                description=f"`The {mention_type.name.lower()} does not have a specific custom prompt set.`",
                color=await ctx.embed_color())
        else:
            embed = discord.Embed(
                title=title,
                description=truncate_prompt(prompt),
                color=await ctx.embed_color()
            )
            embed.add_field(name="Tokens", value=await get_tokens(self.config, ctx, prompt))
        await ctx.send(embed=embed)

    @prompt_show.command(name="members", aliases=["users"])
    async def show_user_prompts(self, ctx: commands.Context):
        await self._show_prompts(ctx, ctx.guild.members, MentionType.USER)

    @prompt_show.command(name="roles")
    async def show_role_prompts(self, ctx: commands.Context):
        await self._show_prompts(ctx, ctx.guild.roles, MentionType.ROLE)

    @prompt_show.command(name="channels")
    async def show_channel_prompts(self, ctx: commands.Context):
        await self._show_prompts(ctx, ctx.guild.channels, MentionType.CHANNEL)

    @prompt_show.command(name="server", aliases=["guild"])
    async def show_server_prompt(self, ctx: commands.Context):
        prompt = await self.config.guild(ctx.guild).custom_text_prompt() or await self.config.custom_text_prompt() or DEFAULT_PROMPT
        embed = discord.Embed(
            title=f"The prompt for this server is:",
            description=truncate_prompt(prompt),
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await get_tokens(self.config, ctx, prompt))
        await ctx.send(embed=embed)

    # -------------------- PRESETS --------------------

    @prompt.group(name="preset")
    async def prompt_preset(self, _: commands.Context):
        """Manage presets for the current server"""
        pass

    @prompt_preset.command(name="show", aliases=["list"])
    async def show_presets(self, ctx: commands.Context):
        presets = json.loads(await self.config.guild(ctx.guild).presets())
        if not presets:
            return await ctx.send("No presets set for this server")
        pages = []
        for preset, prompt in presets.items():
            page = discord.Embed(
                title=f"Preset `{preset}`",
                description=truncate_prompt(prompt),
                color=await ctx.embed_color())
            page.add_field(name="Tokens", value=await get_tokens(self.config, ctx, prompt))
            pages.append(page)
        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")
        await SimpleMenu(pages).start(ctx)

    @prompt_preset.command(name="add", aliases=["a"])
    async def add_preset(self, ctx: commands.Context, *, prompt: str):
        presets = json.loads(await self.config.guild(ctx.guild).presets())
        split = prompt.split("|", 1)
        if not len(split) == 2:
            return await ctx.send("Invalid format. Use `|` to separate preset name from prompt. eg. `preset_name|prompt text`")
        preset, prompt = split
        for channel in ctx.guild.channels:
            if channel.name.lower() == preset.lower():
                return await ctx.send(f"Cannot use `{preset}` as a preset name as it conflicts with channel <#{channel.id}>")
        if preset in presets:
            return await ctx.send("That preset name already exists.")
        if len(prompt) > await self.config.max_prompt_length() and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f"Prompt too long. Max length is {await self.config.max_prompt_length()} characters.")
        presets[preset] = prompt
        await self.config.guild(ctx.guild).presets.set(json.dumps(presets))
        embed = discord.Embed(
            title=f"Added preset `{preset}`",
            description=truncate_prompt(prompt),
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await get_tokens(self.config, ctx, prompt))
        return await ctx.send(embed=embed)

    @prompt_preset.command(name="remove", aliases=["rm", "delete"])
    async def remove_preset(self, ctx: commands.Context, preset: str):
        presets = json.loads(await self.config.guild(ctx.guild).presets())
        if preset not in presets:
            return await ctx.send("That preset name does not exist.")
        if preset == "cynical":
            return await ctx.send("Cannot remove the default preset.")
        prompt = presets.pop(preset)
        await self.config.guild(ctx.guild).presets.set(json.dumps(presets))
        embed = discord.Embed(
            title=f"Removed preset `{preset}`",
            description=truncate_prompt(prompt),
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    # -------------------- CUSTOM PROMPT --------------------

    @prompt.command(name="set", aliases=["custom", "customize"])
    async def prompt_custom(self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS], *, prompt: Optional[str]):
        """Set a custom prompt or preset for the server (or channel/role/member)"""
        if not prompt and ctx.message.attachments:
            if not ctx.message.attachments[0].filename.endswith(".txt"):
                return await ctx.send(":warning: Invalid attachment. Must be a `.txt` file.")
            prompt = (await ctx.message.attachments[0].read()).decode("utf-8")

        if not prompt:
            prompt = None

        if prompt and len(prompt) > await self.config.max_prompt_length() and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f":warning: Prompt too long. Max length is {await self.config.max_prompt_length()} characters.")

        presets = json.loads(await self.config.guild(ctx.guild).presets())
        if prompt and prompt in presets:
            prompt = presets[prompt]

        mention_type = get_mention_type(mention)
        config_attr = get_config_attribute(self.config, mention_type, ctx, mention)
        if not config_attr:
            return await ctx.send(":warning: Invalid mention type provided.")

        if not prompt:
            await config_attr.custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for this {mention_type.name.lower()} will no longer use a custom prompt.")

        await config_attr.custom_text_prompt.set(prompt)
        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at

        embed = discord.Embed(
            title=f"The {mention_type.name.lower()} will use the custom prompt:",
            description=f"{truncate_prompt(prompt)}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await get_tokens(self.config, ctx, prompt))
        return await ctx.send(embed=embed)

    # -------------------- BLACKLIST --------------------

    @prompt.group(name="blacklist", invoke_without_command=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def prompt_blacklist(self, ctx: commands.Context):
        """Manage phrases that are blacklisted from prompts"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `add`, `remove`, or `list`.")

    @prompt_blacklist.command(name="add")
    async def add_blacklist_phrase(self, ctx: commands.Context, *, phrase: str):
        phrases = await self.config.guild(ctx.guild).removelist_regexes()
        if phrase in phrases:
            return await ctx.send("That phrase is already blacklisted.")
        phrases.append(phrase)
        await self.config.guild(ctx.guild).removelist_regexes.set(phrases)
        await ctx.send(f"Added `{phrase}` to the blacklist.")

    @prompt_blacklist.command(name="remove", aliases=["rm", "delete"])
    async def remove_blacklist_phrase(self, ctx: commands.Context, *, phrase: str):
        phrases = await self.config.guild(ctx.guild).removelist_regexes()
        if phrase not in phrases:
            return await ctx.send("That phrase is not in the blacklist.")
        phrases.remove(phrase)
        await self.config.guild(ctx.guild).removelist_regexes.set(phrases)
        await ctx.send(f"Removed `{phrase}` from the blacklist.")

    @prompt_blacklist.command(name="list", aliases=["show"])
    async def list_blacklist_phrases(self, ctx: commands.Context):
        phrases = await self.config.guild(ctx.guild).removelist_regexes()
        if not phrases:
            return await ctx.send("No phrases are currently blacklisted.")
        embed = discord.Embed(
            title="Blacklisted Phrases",
            description="\n".join(f"`{p}`" for p in phrases),
            color=await ctx.embed_color()
        )
        await ctx.send(embed=embed)
