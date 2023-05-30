import logging
import re
from typing import Optional

import discord
import openai
from redbot.core import checks, commands

from ai_user.abc import MixinMeta
from ai_user.settings.image import ImageSettings
from ai_user.settings.prompt import PromptSettings
from ai_user.settings.response import ResponseSettings

logger = logging.getLogger("red.bz_cogs.ai_user")


class Settings(ImageSettings, PromptSettings, ResponseSettings, MixinMeta):
    @commands.group()
    @commands.guild_only()
    async def ai_user(self, _):
        """ Utilize OpenAI to reply to messages and images in approved channels """
        pass

    @ai_user.command()
    async def forget(self, ctx: commands.Context):
        """ Forces the AI to forget the current conversation up to this point """
        if not ctx.channel.permissions_for(ctx.author).manage_messages\
                and not await self.config.guild(ctx.guild).public_forget():
            return await ctx.react_quietly("❌")

        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        await ctx.react_quietly("✅")

    @ai_user.command(aliases=["settings", "showsettings"])
    async def config(self, ctx: commands.Context):
        """ Returns current config """
        config = await self.config.guild(ctx.guild).get_raw()
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        channels = [f"<#{channel_id}>" for channel_id in whitelist]

        embed = discord.Embed(title="AI User Settings", color=await ctx.embed_color())

        embed.add_field(name="Model", inline=True, value=config['model'])
        embed.add_field(name="Reply Percent", inline=True, value=f"{config['reply_percent'] * 100:.2f}%")
        embed.add_field(name="Scan Images", inline=True, value=config['scan_images'])
        embed.add_field(name="Scan Image Mode", inline=True, value=config['scan_images_mode'])
        embed.add_field(name="Scan Image Max Size", inline=True,
                        value=f"{config['max_image_size'] / 1024 / 1024:.2f} MB")
        embed.add_field(name="Max History Size", inline=True, value=f"{config['messages_backread']} messages")
        embed.add_field(name="Max History Gap", inline=True, value=f"{config['messages_backread_seconds']} seconds")
        embed.add_field(name="Always Reply if Pinged", inline=True, value=config['reply_to_mentions_replies'])
        embed.add_field(name="Public Forget Command", inline=True, value=config['public_forget'])
        embed.add_field(name="Whitelisted Channels", inline=False, value=' '.join(channels) if channels else "None")

        regex_embed = discord.Embed(title="AI User Regex Settings", color=await ctx.embed_color())
        removelist_regexes = config['removelist_regexes']
        if isinstance(config['removelist_regexes'], list):
            total_length = 0
            removelist_regexes = []

            for item in config['removelist_regexes']:
                if total_length + len(item) <= 1000:
                    removelist_regexes.append(item)
                    total_length += len(item)
                else:
                    removelist_regexes.append("More regexes not shown...")
                    break

        blocklist_regexes = config['blocklist_regexes']
        if isinstance(config['blocklist_regexes'], list):
            total_length = 0
            blocklist_regexes = []

            for item in config['blocklist_regexes']:
                if total_length + len(item) <= 1000:
                    blocklist_regexes.append(item)
                    total_length += len(item)
                else:
                    blocklist_regexes.append("More regexes not shown...")
                    break

        regex_embed.add_field(name="Block Regex list", value=f"`{blocklist_regexes}`")
        regex_embed.add_field(name="Remove Regex list", value=f"`{removelist_regexes}`")
        regex_embed.add_field(name="Ignore Regex", value=config['ignore_regex'])

        await ctx.send(embed=embed)
        return await ctx.send(embed=regex_embed)

    @ai_user.command()
    @checks.is_owner()
    async def percent(self, ctx: commands.Context, new_value: float):
        """ Change the bot's response chance """
        await self.config.guild(ctx.guild).reply_percent.set(new_value / 100)
        self.reply_percent[ctx.guild.id] = new_value / 100
        embed = discord.Embed(
            title="Chance that the bot will reply on this server is now:",
            description=f"{new_value:.2f}%",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def add(self, ctx: commands.Context, channel: discord.TextChannel):
        """ Add a channel to the whitelist to allow the bot to reply in """
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

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """ Remove a channel from the whitelist """
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

    @ai_user.command()
    @checks.is_owner()
    async def model(self, ctx: commands.Context, new_value: str):
        """ Changes chat completion model """
        if not openai.api_key:
            await self.initalize_openai(ctx)

        models_list = openai.Model.list()

        if openai.api_base.startswith("https://api.openai.com/"):
            gpt_models = [model.id for model in models_list['data'] if model.id.startswith('gpt')]
        else:
            gpt_models = [model.id for model in models_list['data']]

        if new_value not in gpt_models:
            return await ctx.send(f"Invalid model. Choose from: {', '.join(gpt_models)}")
        await self.config.guild(ctx.guild).model.set(new_value)
        embed = discord.Embed(
            title="This server's chat model is now set to:",
            description=new_value,
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @ai_user.command(name="force_reply_to_mentions", aliases=["mentions_replies"])
    @checks.is_owner()
    async def force_reply_to_mentions(self, ctx: commands.Context):
        """ Toggles if the bot will always reply to mentions/replies """
        value = not await self.config.guild(ctx.guild).reply_to_mentions_replies()
        await self.config.guild(ctx.guild).reply_to_mentions_replies.set(value)
        embed = discord.Embed(
            title="Always replying to mentions or replies for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def ignore(self, ctx: commands.Context, *, regex_pattern: Optional[str]):
        """ Messages matching this regex won't be replied to by the AI """
        if not regex_pattern:
            await self.config.guild(ctx.guild).ignore_regex.set(None)
            self.ignore_regex[ctx.guild.id] = None
            return await ctx.send("The ignore regex has been cleared.")
        try:
            self.ignore_regex[ctx.guild.id] = re.compile(regex_pattern)
        except:
            return await ctx.send("Sorry, but that regex pattern seems to be invalid.")
        await self.config.guild(ctx.guild).ignore_regex.set(regex_pattern)
        embed = discord.Embed(
            title="The ignore regex is now:",
            description=f"`{regex_pattern}`",
            color=await ctx.embed_color())
        await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def public_forget(self, ctx: commands.Context):
        """ Toggles whether anyone can use the forget command, or only moderators """
        value = not await self.config.guild(ctx.guild).public_forget()
        await self.config.guild(ctx.guild).public_forget.set(value)
        embed = discord.Embed(
            title="Anyone can use the forget command:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)
