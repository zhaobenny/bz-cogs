
import datetime
import logging
import random

import discord
import openai
from redbot.core import Config, commands

from ai_user.abc import CompositeMetaClass
from ai_user.prompts.prompt_factory import create_prompt_instance
from ai_user.response.response import generate_response
from ai_user.settings import settings

logger = logging.getLogger("red.bz_cogs.ai_user")


class AI_User(settings, commands.Cog, metaclass=CompositeMetaClass):

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

        return await generate_response(message, self.config, prompt)

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

        return await generate_response(after, self.config, prompt)

    async def is_common_valid_reply(self, message) -> bool:
        """ Run some common checks to see if a message is valid for the bot to reply to """
        if not message.guild:
            return False

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return False

        if message.author.bot:
            return False

        if not self.cached_options.get(message.guild.id):
            await self.cache_guild_options(message)

        if (message.channel.id not in self.cached_options[message.guild.id].get("channels_whitelist")):
            return False

        if not openai.api_key:
            await self.initalize_openai(message)

        if not openai.api_key:
            return False

        return True

    async def is_bot_mentioned_or_replied(self, message) -> bool:
        if self.bot.user in message.mentions:
            return True
        elif (message.reference and (await message.channel.fetch_message(message.reference.message_id)).author == self.bot.user):
            return True
        return False

    async def initalize_openai(self, message):
        openai.api_key = (await self.bot.get_shared_api_tokens("openai")).get("api_key")
        if not openai.api_key:
            return await message.channel.send("OpenAI API key not set for ai_user. Please set it with `[p]set api openai api_key,API_KEY`")
