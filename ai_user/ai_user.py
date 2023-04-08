
import datetime
import importlib
import json
import logging
import random

import discord
import openai
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.chat_formatting import box

from ai_user.prompts.constants import DEFAULT_PROMPT, PRESETS
from ai_user.prompts.prompt_factory import create_prompt_instance
from ai_user.response.response import generate_response

logger = logging.getLogger("red.bz_cogs.ai_user")


class AI_User(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.config = Config.get_conf(self, identifier=754070)
        self.cached_options = {}

        default_global = {
            "scan_images": False,
            "model": "gpt-3.5-turbo",
            "filter_responses": True,
        }

        default_guild = {
            "channels_whitelist": [],
            "custom_text_prompt": None,
            "reply_percent": 0.5,
        }

        default_member = {
            "custom_text_prompt": None,
        }

        self.config.register_member(**default_member)
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name, api_tokens):
        if service_name == "openai":
            openai.api_key = api_tokens.get("api_key")

    @commands.group()
    async def ai_user(self, _):
        pass

    @ai_user.command()
    async def config(self, message):
        """ Returns current config """
        whitelist = await self.config.guild(message.guild).channels_whitelist()
        channels = [f"<#{channel_id}>" for channel_id in whitelist]

        embed = discord.Embed(title="AI User Settings")
        embed.add_field(name="Scan Images", value=await self.config.scan_images(), inline=False)
        embed.add_field(name="Model", value=await self.config.model(), inline=False)
        embed.add_field(name="Filter Responses", value=await self.config.filter_responses(), inline=False)
        embed.add_field(name="Server Reply Percent", value=f"{await self.config.guild(message.guild).reply_percent() * 100}%", inline=False)
        embed.add_field(name="Server Whitelisted Channels", value=" ".join(
            channels) if channels else "None", inline=False)
        return await message.send(embed=embed)

    @ai_user.command()
    @checks.is_owner()
    async def scan_images(self, ctx):
        """ Toggle image scanning (req. cpu usage / tesseract) """
        try:
            importlib.import_module("pytesseract")
            importlib.import_module("torch")
            importlib.import_module("transformers")
            value = not await self.config.scan_images()
            await self.config.scan_images.set(value)
            embed = discord.Embed(
                title="⚠️ WILL CAUSE HEAVY CPU LOAD ⚠️")
            embed.add_field(name="Scanning Images now set to", value=value)
            return await ctx.send(embed=embed)
        except:
            await self.config.scan_images.set(False)
            await ctx.send("Image processing dependencies not available. Please install them (see cog README.md) to use this feature.")

    @ai_user.command()
    @checks.is_owner()
    async def percent(self, ctx, new_value):
        """Change the bot's response chance for this server """
        try:
            new_value = float(new_value)
        except ValueError:
            return await ctx.send("Value must be a number")
        await self.config.guild(ctx.guild).reply_percent.set(new_value / 100)
        await self.cache_guild_options(ctx)
        embed = discord.Embed(
            title="The chance that the bot will reply on this server is now set to")
        embed.add_field(name="", value=f"{new_value}%")
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.is_owner()
    async def model(self, ctx, new_value):
        """ Changes global chat completion model """
        if not openai.api_key:
            await self.initalize_openai(ctx)

        models_list = openai.Model.list()
        gpt_models = [model.id for model in models_list['data']
                      if model.id.startswith('gpt')]

        if new_value not in gpt_models:
            return await ctx.send(f"Invalid model. Choose from: {', '.join(gpt_models)}")

        await self.config.model.set(new_value)
        embed = discord.Embed(
            title="The default model is now set to")
        embed.add_field(name="", value=new_value)
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.is_owner()
    async def filter_responses(self, ctx):
        """ Toggles rudimentary filtering of canned replies """
        value = not await self.config.filter_responses()
        await self.config.filter_responses.set(value)
        embed = discord.Embed(
            title="Filtering canned responses now set to")
        embed.add_field(name="", value=value)
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def add(self, ctx, channel: discord.TextChannel):
        """ Add a channel to the whitelist to allow the bot to reply in"""
        if channel is None:
            return await ctx.send("Invalid channel mention, use #channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id in new_whitelist:
            return await ctx.send("Channel already in whitelist")
        new_whitelist.append(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        await self.cache_guild_options(ctx)
        embed = discord.Embed(title="The server whitelist is now")
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.add_field(name="", value=" ".join(
            channels) if channels else "None")
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def remove(self, ctx, channel: discord.TextChannel):
        """ Remove a channel from the whitelist"""
        if channel is None:
            return await ctx.send("Invalid channel mention, use #channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id not in new_whitelist:
            return await ctx.send("Channel not in whitelist")
        new_whitelist.remove(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        await self.cache_guild_options(ctx)
        embed = discord.Embed(title="The server whitelist is now")
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.add_field(name="", value=" ".join(
            channels) if channels else "None")
        return await ctx.send(embed=embed)

    @ai_user.group()
    @checks.is_owner()
    async def prompt(self, _):
        """ Change the prompt settings for the current server"""
        pass

    @prompt.command()
    @checks.is_owner()
    async def reset(self, ctx):
        """ Reset ALL prompts (inc. user) to default (cynical)"""
        await self.config.guild(ctx.guild).custom_text_prompt.set(None)
        for member in ctx.guild.members:
            await self.config.member(member).custom_text_prompt.set(None)
        embed = discord.Embed(title="All prompts resetted")
        return await ctx.send(embed=embed)

    @prompt.group()
    async def show(self, _):
        """ Show prompts """
        pass

    @show.command()
    @checks.admin()
    async def server(self, ctx):
        """ Show current server prompt"""
        custom_text_prompt = await self.config.guild(ctx.guild).custom_text_prompt()
        res = "The prompt for this server is:\n"
        if custom_text_prompt:
            res += box(f"{self._truncate_prompt(custom_text_prompt)}")
        else:
            res += box(f"{DEFAULT_PROMPT}")
        return await ctx.send(res)

    @show.command()
    @checks.admin()
    async def users(self, ctx):
        """ Show all users with custom prompts """
        pages = []
        for member in ctx.guild.members:
            custom_text_prompt = await self.config.member(member).custom_text_prompt()
            if custom_text_prompt:
                page = f"The prompt for user {member.name} is:"
                page += box(f"\n{self._truncate_prompt(custom_text_prompt)}")
                pages.append(page)
        if not pages:
            return await ctx.send("No users with custom prompts")
        if len(pages) == 1:
            return await ctx.send(pages[0])
        return await menu(ctx, pages, DEFAULT_CONTROLS)

    @prompt.command()
    @checks.admin()
    async def preset(self, ctx, preset):
        """ List presets using 'list', or set a preset """
        if preset == 'list':
            embed = discord.Embed(title="Presets", description="Use `[p]prompt preset <preset>` to set a preset")
            embed.add_field(name="Available presets", value="\n".join(PRESETS.keys()), inline=False)
            return await ctx.send(embed=embed)
        if preset not in PRESETS:
            return await ctx.send("Invalid preset. Use `list` to see available presets")
        await self.config.guild(ctx.guild).custom_text_prompt.set(PRESETS[preset])
        res = "The prompt for this server is now changed to:\n"
        res += box(f"{PRESETS[preset]}")
        return await ctx.send(res)

    @prompt.group()
    @checks.is_owner()
    async def custom(self, _):
        """ Customize the prompt sent to OpenAI """
        pass

    @custom.command()
    @checks.is_owner()
    async def guild(self, ctx, prompt : str = ""):
        """ Set custom prompt for current guild (Enclose with "") """
        if prompt == "":
            await self.config.guild(ctx.guild).custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for this server is now reset to the default prompt")
        await self.config.guild(ctx.guild).custom_text_prompt.set(prompt)
        res = "The prompt for this server is now changed to:\n"
        res += box(f"{self._truncate_prompt(prompt)}")
        return await ctx.send(res)

    @custom.command()
    @checks.is_owner()
    async def user(self, ctx, member: discord.Member, prompt : str = ""):
        """ Set custom prompt per user in current guild (Enclose with "") """
        if prompt == "":
            await self.config.member(member).custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for user {member.mention} is now reset to default server prompt")
        await self.config.member(member).custom_text_prompt.set(prompt)
        res = f"The prompt for user {member.mention} is now changed to:\n"
        res += box(f"{self._truncate_prompt(prompt)}")
        return await ctx.send(res)


    def _truncate_prompt(self, prompt):
        return prompt[:1900] + "..." if len(prompt) > 1900 else prompt

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if not await self.is_common_valid_reply(message):
            return

        if (await self.is_bot_mentioned_or_replied(message)):
            pass
        elif random.random() > self.cached_options[message.guild.id].get("reply_percent"):
            return

        prompt_instance = await create_prompt_instance(message, self.config)
        prompt = await prompt_instance.get_prompt()

        if prompt is None:
            return

        return await self.sent_reply(message, prompt)

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """ Catch embed updates """
        if not await self.is_common_valid_reply(before):
            return

        time_diff = datetime.datetime.utcnow() - after.created_at
        if not (time_diff.total_seconds() <= 10):
            return

        if random.random() > self.cached_options[before.guild.id].get("reply_percent"):
            return

        prompt = None
        if len(before.embeds) != len(after.embeds):
            prompt_instance = await create_prompt_instance(after, self.config)
            prompt = await prompt_instance.get_prompt()

        if prompt is None:
            return

        return await self.sent_reply(after, prompt)

    async def sent_reply(self, message, prompt, direct_reply=False):
        """ Generates the reply using OpenAI and sends the result """
        logger.debug(
            f"Replying to message \"{message.content}\" in {message.guild.name} with prompt: \n{json.dumps(prompt, indent=4)}")
        if not openai.api_key:
            await self.initalize_openai(message)
        if not openai.api_key:
            return

        direct_reply, response = await generate_response(
            message, self.config, prompt)

        if response == "😶":
            return await message.add_reaction("😶")

        async with message.channel.typing():
            if direct_reply:
                return await message.reply(response, mention_author=False)
            else:
                return await message.channel.send(response)

    async def is_common_valid_reply(self, message) -> bool:
        """ Run some common checks to see if a message is valid for the bot to reply to """
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return False

        if message.author.bot:
            return False

        if not self.cached_options.get(message.guild.id):
            await self.cache_guild_options(message)

        if (message.channel.id not in self.cached_options[message.guild.id].get("channels_whitelist")):
            return False

        return True

    async def cache_guild_options(self, message):
        self.cached_options[message.guild.id] = {
            "channels_whitelist": await self.config.guild(message.guild).channels_whitelist(),
            "reply_percent": await self.config.guild(message.guild).reply_percent(),
        }

    async def is_bot_mentioned_or_replied(self, message) -> bool:
        if self.bot.user in message.mentions:
            return True
        elif (message.reference and (await message.channel.fetch_message(message.reference.message_id)).author == self.bot.user):
            return True
        return False

    async def initalize_openai(self, message):
        openai.api_key = (await self.bot.get_shared_api_tokens("openai")).get("api_key")
        if not openai.api_key:
            return await message.channel.send("OpenAI API key not set. Please set it with `[p]set api openai api_key,API_KEY`")
