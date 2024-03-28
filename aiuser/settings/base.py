import json
import logging
from typing import Optional, Union

import discord
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu

from aiuser.abc import MixinMeta
from aiuser.common.constants import FUNCTION_CALLING_SUPPORTED_MODELS
from aiuser.common.enums import MentionType
from aiuser.common.utilities import (get_enabled_tools,
                                     is_using_openai_endpoint,
                                     is_using_openrouter_endpoint)
from aiuser.settings.functions import FunctionCallingSettings
from aiuser.settings.image_request import ImageRequestSettings
from aiuser.settings.image_scan import ImageScanSettings
from aiuser.settings.owner import OwnerSettings
from aiuser.settings.prompt import PromptSettings
from aiuser.settings.random_message import RandomMessageSettings
from aiuser.settings.response import ResponseSettings
from aiuser.settings.triggers import TriggerSettings
from aiuser.settings.utilities import get_config_attribute, get_mention_type

logger = logging.getLogger("red.bz_cogs.aiuser")


class Settings(
    PromptSettings,
    ImageScanSettings,
    ImageRequestSettings,
    ResponseSettings,
    TriggerSettings,
    OwnerSettings,
    RandomMessageSettings,
    FunctionCallingSettings,
    MixinMeta,
):
    @commands.group(aliases=["ai_user"])
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def aiuser(self, _):
        """Utilize OpenAI to reply to messages and images in approved channels and by opt-in users"""
        pass

    @aiuser.command(aliases=["lobotomize"])
    async def forget(self, ctx: commands.Context):
        """Forces the bot to forget the current conversation up to this point

        This is useful if the LLM is stuck doing unwanted behaviour or giving undesirable results.
        See `[p]aiuser triggers public_forget` to allow non-admins to use this command.
        """
        if (
            not ctx.channel.permissions_for(ctx.author).manage_messages
            and not await self.config.guild(ctx.guild).public_forget()
        ):
            return await ctx.react_quietly("❌")

        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        await ctx.react_quietly("✅")

    @aiuser.command(aliases=["settings", "showsettings"])
    async def config(self, ctx: commands.Context):
        """Returns current config

        (Current config per server)
        """
        config = await self.config.guild(ctx.guild).get_raw()
        glob_config = await self.config.get_raw()
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        channels = [f"<#{channel_id}>" for channel_id in whitelist]
        embeds = []

        main_embed = discord.Embed(
            title="AI User Settings", color=await ctx.embed_color()
        )

        main_embed.add_field(name="Model", inline=True, value=f"`{config['model']}`")
        main_embed.add_field(
            name="Server Reply Percent",
            inline=True,
            value=f"`{config['reply_percent'] * 100:.2f}`%",
        )

        main_embed.add_field(
            name="Opt In By Default", inline=True, value=f"`{config['optin_by_default']}`"
        )
        main_embed.add_field(
            name="Always Reply if Pinged",
            inline=True,
            value=f"`{config['reply_to_mentions_replies']}`",
        )
        main_embed.add_field(
            name="Max History Size",
            inline=True,
            value=f"`{config['messages_backread']}` messages",
        )
        main_embed.add_field(
            name="Max History Gap",
            inline=True,
            value=f"`{config['messages_backread_seconds']}` seconds",
        )

        main_embed.add_field(
            name="Whitelisted Channels",
            inline=True,
            value=" ".join(channels) if channels else "`None`",
        )

        endpoint_url = str(glob_config["custom_openai_endpoint"] or "")
        if endpoint_url.startswith("https://openrouter.ai/api/"):
            endpoint_text = "Using [OpenRouter](https://openrouter.ai) endpoint"
        elif endpoint_url:
            endpoint_text = "Using an custom endpoint"
        else:
            endpoint_text = "Using the official [OpenAI](https://openai.com/) endpoint"
        main_embed.add_field(name="LLM Endpoint",
                             inline=True, value=endpoint_text)

        main_embed.add_field(
            name="",
            inline=False,
            value="",
        )

        main_embed.add_field(
            name="Function Calling",
            inline=True,
            value=f"`{config['function_calling']}`",
        )

        main_embed.add_field(
            name="Enabled Functions",
            inline=True,
            value=f"`{len(await get_enabled_tools(self.config, ctx))}`",
        )

        main_embed.add_field(
            name="",
            inline=True,
            value="",
        )

        main_embed.add_field(
            name="Scan Images", inline=True, value=f"`{config['scan_images']}`"
        )
        main_embed.add_field(
            name="Scan Image Mode", inline=True, value=f"`{config['scan_images_mode']}`"
        )
        main_embed.add_field(
            name="Scan Image Max Size",
            inline=True,
            value=f"`{config['max_image_size'] / 1024 / 1024:.2f}` MB",
        )

        main_embed.add_field(
            name="Image Requests", value=f"`{config['image_requests']}`", inline=True)

        main_embed.add_field(
            name="Image Req. Less Calls",
            value=f"`{config['image_requests_reduced_llm_calls']}`",
            inline=True,
        )

        main_embed.add_field(
            name="",
            value="",
            inline=True,
        )

        whitelisted_trigger = bool(
            config["members_whitelist"] or config["roles_whitelist"])

        main_embed.add_field(
            name="Only Whitelist Trigger",
            inline=True,
            value=f"`{whitelisted_trigger}`",
        )

        main_embed.add_field(
            name="Whitelisted Members",
            inline=True,
            value=" ".join(
                [f"<@{member_id}>" for member_id in config["members_whitelist"]]
            ) or "`None`",
        )

        main_embed.add_field(
            name="Whitelisted Roles",
            inline=True,
            value=" ".join(
                [f"<@&{role_id}>" for role_id in config["roles_whitelist"]]
            ) or "`None`",
        )

        removelist_regexes = config["removelist_regexes"]
        regexes_num = 0
        if removelist_regexes is not None:
            regexes_num = len(removelist_regexes)
        main_embed.add_field(
            name="Remove list", value=f"`{regexes_num}` regexes set"
        )
        main_embed.add_field(name="Ignore Regex",
                             value=f"`{config['ignore_regex']}`")
        main_embed.add_field(
            name="Public Forget Command", inline=True, value=f"`{config['public_forget']}`"
        )
        embeds.append(main_embed)

        parameters = config["parameters"]
        if parameters is not None:
            parameters = json.loads(parameters)
            parameters_embed = discord.Embed(
                title="Custom Parameters to Endpoint", color=await ctx.embed_color()
            )
            for key, value in parameters.items():
                parameters_embed.add_field(
                    name=key, value=f"```{json.dumps(value, indent=4)}```", inline=False
                )
            embeds.append(parameters_embed)

        for embed in embeds:
            await ctx.send(embed=embed)
        return

    @aiuser.command()
    @checks.is_owner()
    async def percent(self, ctx: commands.Context, mention: Optional[Union[discord.Member, discord.Role, discord.TextChannel, discord.VoiceChannel, discord.StageChannel]], percent: Optional[float]):
        """Change the bot's response chance for a server (or a provided user, role, and channel)

        If multiple percentage can be used, the most specific percentage will be used, eg. it will go for: member > role > channel > server

        **Arguments**
            - `mention` (Optional) A mention of a user, role, or channel
            - `percent` (Optional) A number between 1 and 100, if omitted, will reset to using other percentages
        (Setting is per server)
        """
        mention_type = get_mention_type(mention)
        config_attr = get_config_attribute(self.config, mention_type, ctx, mention)
        if not percent and mention_type == MentionType.SERVER:
            return await ctx.send(":warning: No percent provided")
        if percent:
            await config_attr.reply_percent.set(percent / 100)
            desc = f"{percent:.2f}%"
        else:
            await config_attr.reply_percent.set(None)
            desc = "`Custom percent no longer set, will default to other percents`"
        embed = discord.Embed(
            title=f"Chance that the bot will reply on this {mention_type.name.lower()} is now:",
            description=desc,
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @aiuser.command()
    @checks.is_owner()
    async def add(
        self,
        ctx: commands.Context,
        channel: Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel],
    ):
        """Adds a channel to the whitelist

        **Arguments**
            - `channel` A mention of the channel
        """
        if not channel:
            return await ctx.send("Invalid channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id in new_whitelist:
            return await ctx.send("Channel already in whitelist")
        new_whitelist.append(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        self.channels_whitelist[ctx.guild.id] = new_whitelist
        embed = discord.Embed(
            title="The server whitelist is now:", color=await ctx.embed_color()
        )
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.description = "\n".join(channels) if channels else "None"
        return await ctx.send(embed=embed)

    @aiuser.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def remove(
        self,
        ctx: commands.Context,
        channel: Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel],
    ):
        """Remove a channel from the whitelist

        **Arguments**
            - `channel` A mention of the channel
        """
        if not channel:
            return await ctx.send("Invalid channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id not in new_whitelist:
            return await ctx.send("Channel not in whitelist")
        new_whitelist.remove(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        self.channels_whitelist[ctx.guild.id] = new_whitelist
        embed = discord.Embed(
            title="The server whitelist is now:", color=await ctx.embed_color()
        )
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.description = "\n".join(channels) if channels else "None"
        return await ctx.send(embed=embed)

    @aiuser.command()
    @checks.is_owner()
    async def model(self, ctx: commands.Context, model: str):
        """Changes chat completion model

         To see a list of available models, use `[p]aiuser model list`
         (Setting is per server)

        **Arguments**
            - `model` The model to use eg. `gpt-4`
        """
        if not self.openai_client:
            await self.initalize_openai(ctx)

        await ctx.message.add_reaction("🔄")
        models_list = await self.openai_client.models.list()
        await ctx.message.remove_reaction("🔄", ctx.me)

        if is_using_openai_endpoint(self.openai_client):
            models = [
                model.id for model in models_list.data if "gpt" in model.id]
        else:
            models = [model.id for model in models_list.data]

        if model == "list":
            return await self._paginate_models(ctx, models)

        if await self.config.guild(ctx.guild).function_calling() and model not in FUNCTION_CALLING_SUPPORTED_MODELS:
            return await ctx.send(":warning: Can not select model that with no build-in support for function calling!\nSwitch function calling off using `[p]aiuser functions toggle` or select a model that supports function calling.")

        if model not in models:
            await ctx.send(":warning: Not a valid model!")
            return await self._paginate_models(ctx, models)

        await self.config.guild(ctx.guild).model.set(model)
        embed = discord.Embed(
            title="This server's chat model is now set to:",
            description=model,
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    async def _paginate_models(self, ctx, models):
        pagified_models = [models[i: i + 10]
                           for i in range(0, len(models), 10)]
        menu_pages = []

        for models_page in pagified_models:
            embed = discord.Embed(
                title="Available Models",
                color=await ctx.embed_color(),
            )
            embed.description = "\n".join(
                [f"`{model}`" for model in models_page])
            menu_pages.append(embed)

        if is_using_openrouter_endpoint(self.openai_client):
            menu_pages[0].add_field(
                name="For pricing and more details go to:",
                value="https://openrouter.ai/models",
                inline=False,
            )

        if len(menu_pages) == 1:
            return await ctx.send(embed=menu_pages[0])
        for i, page in enumerate(menu_pages):
            page.set_footer(text=f"Page {i+1} of {len(menu_pages)}")
        return (await SimpleMenu(menu_pages).start(ctx))

    @aiuser.command()
    async def optin(self, ctx: commands.Context):
        """Opt in of sending your messages / images to OpenAI or another endpoint (bot-wide)

        This will allow the bot to reply to your messages or using your messages.
        """
        optin = await self.config.optin()
        if ctx.author.id in await self.config.optin():
            return await ctx.send("You are already opted in.")
        optout = await self.config.optout()
        if ctx.author.id in optout:
            optout.remove(ctx.author.id)
            await self.config.optout.set(optout)
        optin.append(ctx.author.id)
        await self.config.optin.set(optin)
        await ctx.send("You are now opted in bot-wide")

    @aiuser.command()
    async def optout(self, ctx: commands.Context):
        """Opt out of sending your messages / images to OpenAI or another endpoint (bot-wide)

        This will prevent the bot from replying to your messages or using your messages.
        """
        optout = await self.config.optout()
        if ctx.author.id in optout:
            return await ctx.send("You are already opted out.")
        optin = await self.config.optin()
        if ctx.author.id in optin:
            optin.remove(ctx.author.id)
            await self.config.optin.set(optin)
        optout.append(ctx.author.id)
        await self.config.optout.set(optout)
        await ctx.send("You are now opted out bot-wide")

    @aiuser.command(name="optinbydefault", alias=["optindefault"])
    @checks.admin_or_permissions(manage_guild=True)
    async def optin_by_default(self, ctx: commands.Context):
        """Toggles whether users are opted in by default in this server

        This command is disabled for servers with more than 150 members.
        """
        if len(ctx.guild.members) > 150:
            # if you STILL want to enable this for a server with more than 150 members
            # add the line below to the specific guild in the cog's settings.json:
            # "optin_by_default": true
            # insert concern about user privacy and getting user consent here
            return await ctx.send(
                "You cannot enable this setting for servers with more than 150 members."
            )
        value = not await self.config.guild(ctx.guild).optin_by_default()
        self.optindefault[ctx.guild.id] = value
        await self.config.guild(ctx.guild).optin_by_default.set(value)
        embed = discord.Embed(
            title="Users are now opted in by default in this server:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)
