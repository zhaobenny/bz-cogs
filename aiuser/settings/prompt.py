import json
import logging
from typing import Optional

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.menus import SimpleMenu

from aiuser.config.defaults import DEFAULT_PROMPT
from aiuser.settings._groups import aiuser
from aiuser.settings.scope import get_settings_target_scope
from aiuser.settings.utilities import (
    add_prompt_metrics_fields,
    confirm_pending,
    truncate_prompt,
)
from aiuser.types.abc import MixinMeta
from aiuser.types.enums import MentionType
from aiuser.types.types import COMPATIBLE_MENTIONS

logger = logging.getLogger("red.bz_cogs.aiuser")


def _set_page_footers(pages: list[discord.Embed]) -> None:
    for index, page in enumerate(pages, start=1):
        footer = page.footer.text or ""
        suffix = f"Page {index} of {len(pages)}"
        page.set_footer(text=f"{footer} | {suffix}" if footer else suffix)


async def _build_prompt_pages(
    ctx: commands.Context,
    services,
    title: str,
    prompt: str,
    *,
    include_metrics: bool = True,
) -> list[discord.Embed]:
    prompt_pages = list(pagify(prompt, page_length=3900)) or [prompt or " "]
    pages = [
        discord.Embed(
            title=title,
            description=prompt_page,
            color=await ctx.embed_color(),
        )
        for prompt_page in prompt_pages
    ]
    if include_metrics:
        await add_prompt_metrics_fields(pages[0], services, ctx, prompt)
    return pages


class PromptSettings(MixinMeta):
    @aiuser.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def prompt(self, _):
        """Change the prompt settings for the current server

        (All subcommands are per server)
        """
        pass

    @prompt.command(name="reset_all", aliases=["reset"])
    async def prompt_reset(self, ctx: commands.Context):
        """Reset ALL prompts in this guild to default (inc. channels and members)"""
        embed = discord.Embed(
            title="Are you sure?",
            description="This will reset *ALL* prompts in this guild to default (including per channel, per role and per member)",
            color=await ctx.embed_color(),
        )
        confirmed, confirm = await confirm_pending(ctx, embed, timeout=10.0)
        if not confirmed:
            return

        self.services.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        await self.config.guild(ctx.guild).custom_text_prompt.set(None)
        for member in ctx.guild.members:
            await self.config.member(member).custom_text_prompt.set(None)
        for channel in ctx.guild.channels:
            await self.config.channel(channel).custom_text_prompt.set(None)
        for role in ctx.guild.roles:
            await self.config.role(role).custom_text_prompt.set(None)
        return await confirm.edit(
            embed=discord.Embed(
                title="All prompts have been reset to default.",
                color=await ctx.embed_color(),
            )
        )

    @prompt.group(name="show", invoke_without_command=True)
    async def prompt_show(
        self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS]
    ):
        """Show the prompt for the server (or provided user/channel)
        **Arguments**
            - `mention` *(Optional)* User or channel
        """
        if mention:
            mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
            prompt = await config_attr.custom_text_prompt()
            title = await self._get_embed_title(mention_type, mention)
        else:
            channel_prompt = await self.config.channel(ctx.channel).custom_text_prompt()
            prompt = (
                channel_prompt
                or await self.config.guild(ctx.guild).custom_text_prompt()
                or await self.config.custom_text_prompt()
                or DEFAULT_PROMPT
            )
            title = f"The prompt for {ctx.channel.mention if channel_prompt else 'this server'} is:"

        if mention and not prompt:
            embed = discord.Embed(
                title=title,
                description=f"`The {mention_type.name.lower()} does not have a specific custom prompt set.`",
                color=await ctx.embed_color(),
            )
            await ctx.send(embed=embed)
        else:
            await self._send_prompt_pages(ctx, title, prompt)

    @prompt_show.command(name="members", aliases=["users"])
    async def show_user_prompts(self, ctx: commands.Context):
        """Show all users with custom prompts"""
        await self._show_prompts(ctx, ctx.guild.members, MentionType.USER)

    @prompt_show.command(name="roles")
    async def show_role_prompts(self, ctx: commands.Context):
        """Show all roles with custom prompts"""
        await self._show_prompts(ctx, ctx.guild.roles, MentionType.ROLE)

    @prompt_show.command(name="channels")
    async def show_channel_prompts(self, ctx: commands.Context):
        """Show all channels with custom prompts"""
        await self._show_prompts(ctx, ctx.guild.channels, MentionType.CHANNEL)

    async def _get_embed_title(self, mention_type: MentionType, entity):
        if mention_type == MentionType.USER:
            return f"The prompt for the user `{entity.display_name}` is:"
        elif mention_type == MentionType.ROLE:
            return f"The prompt for the role `{entity.name}` is:"
        elif mention_type == MentionType.CHANNEL:
            return f"The prompt for {entity.mention} is:"
        else:
            return "The prompt for this server is:"

    async def _send_prompt_pages(
        self, ctx: commands.Context, title: str, prompt: str
    ) -> None:
        pages = await _build_prompt_pages(ctx, self.services, title, prompt)

        if len(pages) == 1:
            await ctx.send(embed=pages[0])
            return

        _set_page_footers(pages)
        await SimpleMenu(pages).start(ctx)

    async def _get_custom_prompt(self, ctx, entity, mention_type: MentionType):
        custom_prompt = None
        if mention_type != MentionType.SERVER:
            _, config_attr = get_settings_target_scope(self, ctx, entity)
            custom_prompt = await config_attr.custom_text_prompt()

        if not custom_prompt:
            return None

        return await _build_prompt_pages(
            ctx,
            self.services,
            await self._get_embed_title(mention_type, entity),
            custom_prompt,
        )

    async def _show_prompts(self, ctx, entities, mention_type: MentionType):
        pages = []
        for entity in entities:
            prompt_pages = await self._get_custom_prompt(ctx, entity, mention_type)
            if prompt_pages:
                pages.extend(prompt_pages)

        if not pages:
            return await ctx.send(
                f"No {mention_type.name.lower()}s with custom prompts"
            )

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])

        _set_page_footers(pages)

        await SimpleMenu(pages).start(ctx)

    @prompt_show.command(name="server", aliases=["guild"])
    async def show_server_prompt(self, ctx: commands.Context):
        """Show the current server prompt"""
        prompt = (
            await self.config.guild(ctx.guild).custom_text_prompt()
            or await self.config.custom_text_prompt()
            or DEFAULT_PROMPT
        )
        await self._send_prompt_pages(ctx, "The prompt for this server is:", prompt)

    @prompt.group(name="preset", invoke_without_command=True)
    async def prompt_preset(self, ctx: commands.Context):
        """Show all presets for the current server"""
        presets = json.loads(await self.config.guild(ctx.guild).presets())
        if not presets:
            return await ctx.send("No presets set for this server")
        pages = []
        for preset, prompt in presets.items():
            pages.extend(
                await _build_prompt_pages(
                    ctx,
                    self.services,
                    f"Preset `{preset}`",
                    prompt,
                )
            )
        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        _set_page_footers(pages)
        await SimpleMenu(pages).start(ctx)

    @prompt_preset.command(name="add", aliases=["a"])
    async def add_preset(self, ctx: commands.Context, name: str, *, prompt: str):
        """Add a named prompt preset

        **Arguments**
            - `name` The preset name
            - `prompt` The preset prompt
        """
        presets = json.loads(await self.config.guild(ctx.guild).presets())
        for channel in ctx.guild.channels:
            if channel.name.lower() == name.lower():
                return await ctx.send(
                    f"Cannot use `{name}` as a preset name because it conflicts with <#{channel.id}>."
                )
        if name in presets:
            return await ctx.send("That preset name already exists.")
        if len(
            prompt
        ) > await self.config.max_prompt_length() and not await ctx.bot.is_owner(
            ctx.author
        ):
            return await ctx.send(
                f"Prompt too long. Max length is {await self.config.max_prompt_length()} characters."
            )
        presets[name] = prompt
        await self.config.guild(ctx.guild).presets.set(json.dumps(presets))
        embed = discord.Embed(
            title=f"Added preset `{name}`",
            description=truncate_prompt(prompt),
            color=await ctx.embed_color(),
        )
        await add_prompt_metrics_fields(embed, self.services, ctx, prompt)
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
            description=truncate_prompt(prompt),
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @prompt.command(name="set", aliases=["custom", "customize"])
    async def prompt_custom(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS],
        *,
        prompt: Optional[str],
    ):
        """Set a custom prompt or preset for the server or a target

        If multiple prompts can be used, the most specific prompt will be used, eg. it will go for: member > role > channel > server.

        Prompts can include variables like `{serverprompt}`, `{channelprompt}`, and `{roleprompt}`.

        **Arguments**
            - `mention` *(Optional)* A specific user or channel
            - `prompt` *(Optional)* The prompt or preset name. May be omitted when attaching a text file.
            - `<ATTACHMENT>` *(Optional)* An `.txt` file to use as the prompt
        """
        if not prompt and ctx.message.attachments:
            if not ctx.message.attachments[0].filename.endswith(".txt"):
                return await ctx.send(
                    ":warning: Invalid attachment. Must be a `.txt` file."
                )
            prompt = (await ctx.message.attachments[0].read()).decode("utf-8")

        if not prompt:
            return await ctx.send("Provide a prompt or attach a `.txt` file.")

        if (
            prompt
            and len(prompt) > await self.config.max_prompt_length()
            and not await ctx.bot.is_owner(ctx.author)
        ):
            return await ctx.send(
                f":warning: Prompt too long. Max length is {await self.config.max_prompt_length()} characters."
            )

        presets = json.loads(await self.config.guild(ctx.guild).presets())
        if prompt and prompt in presets:
            prompt = presets[prompt]

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)

        await config_attr.custom_text_prompt.set(prompt)
        self.services.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at

        embed = discord.Embed(
            title=f"The {mention_type.name.lower()} will use the custom prompt:",
            description=f"{truncate_prompt(prompt)}",
            color=await ctx.embed_color(),
        )
        await add_prompt_metrics_fields(embed, self.services, ctx, prompt)
        return await ctx.send(embed=embed)

    @prompt.command(name="clear")
    async def prompt_clear(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        """Clear a custom prompt so broader prompt settings can apply"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.custom_text_prompt.set(None)
        self.services.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        return await ctx.send(
            f"Custom prompt cleared for this {mention_type.name.lower()}."
        )
