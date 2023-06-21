import json
import logging

import discord
import openai
from redbot.core import checks, commands

from aiuser.abc import MixinMeta
from aiuser.settings.image import ImageSettings
from aiuser.settings.prompt import PromptSettings
from aiuser.settings.response import ResponseSettings
from aiuser.settings.triggers import TriggerSettings

logger = logging.getLogger("red.bz_cogs.aiuser")


class Settings(PromptSettings, ImageSettings, ResponseSettings, TriggerSettings, MixinMeta):

    @commands.group(aliases=["ai_user"])
    @commands.guild_only()
    async def aiuser(self, _):
        """ Utilize OpenAI to reply to messages and images in approved channels and by opt-in users"""
        pass

    @aiuser.command(aliases=["lobotomize"])
    async def forget(self, ctx: commands.Context):
        """ Forces the bot to forget the current conversation up to this point

            This is useful if the LLM is stuck doing unwanted behaviour or giving undesirable results.
            See `[p]aiuser triggers public_forget` to allow non-admins to use this command.
        """
        if not ctx.channel.permissions_for(ctx.author).manage_messages\
                and not await self.config.guild(ctx.guild).public_forget():
            return await ctx.react_quietly("❌")

        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        await ctx.react_quietly("✅")

    @aiuser.command(aliases=["settings", "showsettings"])
    async def config(self, ctx: commands.Context):
        """ Returns current config

            (Current config per server)
        """
        config = await self.config.guild(ctx.guild).get_raw()
        glob_config = await self.config.get_raw()
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        channels = [f"<#{channel_id}>" for channel_id in whitelist]
        embeds = []

        main_embed = discord.Embed(title="AI User Settings", color=await ctx.embed_color())

        main_embed.add_field(name="Model", inline=True, value=config['model'])
        main_embed.add_field(name="Reply Percent", inline=True, value=f"{config['reply_percent'] * 100:.2f}%")
        if config['optin_by_default']:
            main_embed.add_field(name="Opt In By Default", inline=True, value=config['optin_by_default'])
        main_embed.add_field(name="Scan Images", inline=True, value=config['scan_images'])
        main_embed.add_field(name="Scan Image Mode", inline=True, value=config['scan_images_mode'])
        main_embed.add_field(name="Scan Image Max Size", inline=True,
                             value=f"{config['max_image_size'] / 1024 / 1024:.2f} MB")
        main_embed.add_field(name="Max History Size", inline=True, value=f"{config['messages_backread']} messages")
        main_embed.add_field(name="Max History Gap", inline=True,
                             value=f"{config['messages_backread_seconds']} seconds")
        main_embed.add_field(name="Always Reply if Pinged", inline=True, value=config['reply_to_mentions_replies'])
        main_embed.add_field(name="Public Forget Command", inline=True, value=config['public_forget'])
        main_embed.add_field(name="Whitelisted Channels", inline=False,
                             value=' '.join(channels) if channels else "None")
        if glob_config['custom_openai_endpoint']:
            endpoint_text = "Using an custom endpoint"
        else:
            endpoint_text = "Using offical OpenAI endpoint"
        main_embed.add_field(name="LLM Endpoint",
                             inline=False, value=endpoint_text)
        embeds.append(main_embed)

        regex_embed = discord.Embed(title="AI User Regex Settings", color=await ctx.embed_color())
        removelist_regexes = config['removelist_regexes']
        if removelist_regexes is not None:
            regex_embed.add_field(name="Remove list", value=f"{len(removelist_regexes)} regexes set")
        regex_embed.add_field(name="Ignore Regex", value=f"`{config['ignore_regex']}`")
        embeds.append(regex_embed)

        parameters = config["parameters"]
        if parameters is not None:
            parameters = json.loads(parameters)
            parameters_embed = discord.Embed(title="Custom Parameters to Endpoint", color=await ctx.embed_color())
            for key, value in parameters.items():
                parameters_embed.add_field(name=key, value=f"```{json.dumps(value, indent=4)}```", inline=False)
            embeds.append(parameters_embed)

        for embed in embeds:
            await ctx.send(embed=embed)
        return

    @aiuser.command()
    @checks.is_owner()
    async def percent(self, ctx: commands.Context, percent: float):
        """ Change the bot's response chance

            **Arguments**
                - `percent` A number between 0 and 100
            (Setting is per server)
        """
        await self.config.guild(ctx.guild).reply_percent.set(percent / 100)
        self.reply_percent[ctx.guild.id] = percent / 100
        embed = discord.Embed(
            title="Chance that the bot will reply on this server is now:",
            description=f"{percent:.2f}%",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @aiuser.command()
    @checks.is_owner()
    async def add(self, ctx: commands.Context, channel: discord.TextChannel):
        """ Adds a channel to the whitelist

        **Arguments**
            - `channel` A mention of the channel
        """
        if not channel:
            return await ctx.send("Invalid channel mention, use #channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id in new_whitelist:
            return await ctx.send("Channel already in whitelist")
        new_whitelist.append(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        self.channels_whitelist[ctx.guild.id] = new_whitelist
        embed = discord.Embed(title="The server whitelist is now:", color=await ctx.embed_color())
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.description = "\n".join(channels) if channels else "None"
        return await ctx.send(embed=embed)

    @aiuser.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """ Remove a channel from the whitelist

        **Arguments**
            - `channel` A mention of the channel
        """
        if not channel:
            return await ctx.send("Invalid channel mention, use #channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id not in new_whitelist:
            return await ctx.send("Channel not in whitelist")
        new_whitelist.remove(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        self.channels_whitelist[ctx.guild.id] = new_whitelist
        embed = discord.Embed(title="The server whitelist is now:", color=await ctx.embed_color())
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.description = "\n".join(channels) if channels else "None"
        return await ctx.send(embed=embed)

    @aiuser.command()
    @checks.is_owner()
    async def model(self, ctx: commands.Context, model: str):
        """ Changes chat completion model

             To see a list of available models, use `[p]aiuser model list`
             (Setting is per server)

            **Arguments**
                - `model` The model to use eg. `gpt-4`
        """
        if not openai.api_key:
            await self.initalize_openai(ctx)

        models_list = openai.Model.list()

        if openai.api_base.startswith("https://api.openai.com/"):
            gpt_models = [model.id for model in models_list['data'] if model.id.startswith('gpt')]
        else:
            gpt_models = [model.id for model in models_list['data']]

        if model == 'list':
            embed = discord.Embed(title="Available Models", color=await ctx.embed_color())
            embed.description = '\n'.join([f"`{model}`" for model in gpt_models])
            return await ctx.send(embed=embed)

        if model not in gpt_models:
            await ctx.send(":warning: Not a valid model! :warning:")
            embed = discord.Embed(title="Available Models", color=await ctx.embed_color())
            embed.description = '\n'.join([f"`{model}`" for model in gpt_models])
            return await ctx.send(embed=embed)

        await self.config.guild(ctx.guild).model.set(model)
        embed = discord.Embed(
            title="This server's chat model is now set to:",
            description=model,
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @aiuser.command()
    async def optin(self, ctx: commands.Context):
        """ Opt in of sending your messages / images to OpenAI or another endpoint (bot-wide)

            This will allow the bot to reply to your messages or using your messages.
        """
        optin = await self.config.optin()
        if ctx.author.id in await self.config.optin():
            return await ctx.send("You are already opted in.")
        optout = await self.config.optout()
        if ctx.author.id in optout:
            optout.remove(ctx.author.id)
            await self.config.optout.set(optout)
            self.optout_users.remove(ctx.author.id)
        optin.append(ctx.author.id)
        self.optin_users.append(ctx.author.id)
        await self.config.optin.set(optin)
        await ctx.send("You are now opted in bot-wide")

    @aiuser.command()
    async def optout(self, ctx: commands.Context):
        """ Opt out of sending your messages / images to OpenAI or another endpoint (bot-wide)

            This will prevent the bot from replying to your messages or using your messages.
        """
        optout = await self.config.optout()
        if ctx.author.id in optout:
            return await ctx.send("You are already opted out.")
        optin = await self.config.optin()
        if ctx.author.id in optin:
            optin.remove(ctx.author.id)
            await self.config.optin.set(optin)
            self.optin_users.remove(ctx.author.id)
        optout.append(ctx.author.id)
        await self.config.optout.set(optout)
        self.optout_users.append(ctx.author.id)
        await ctx.send("You are now opted out bot-wide")

    @aiuser.command(name="optinbydefault", alias=["optindefault"])
    @checks.admin_or_permissions(manage_guild=True)
    async def optin_by_default(self, ctx: commands.Context):
        """ Toggles whether users are opted in by default in this server

            This command is disabled for servers with more than 150 members.
        """
        if len(ctx.guild.members) > 150:
            return await ctx.send("You cannot enable this setting for servers with more than 150 members.")
        value = not await self.config.guild(ctx.guild).optin_by_default()
        self.optindefault[ctx.guild.id] = value
        await self.config.guild(ctx.guild).optin_by_default.set(value)
        embed = discord.Embed(
            title="Users are now opted in by default in this server:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)
