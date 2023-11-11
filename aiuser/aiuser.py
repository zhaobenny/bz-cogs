import asyncio
import json
import logging
import random
import re
from datetime import datetime

import discord
from openai import AsyncOpenAI
from redbot.core import Config, app_commands, commands
from redbot.core.bot import Red

from aiuser.abc import CompositeMetaClass
from aiuser.common.cache import Cache
from aiuser.common.constants import (
    DEFAULT_PRESETS,
    DEFAULT_REMOVE_PATTERNS,
    DEFAULT_REPLY_PERCENT,
    DEFAULT_TOPICS,
    MAX_MESSAGE_LENGTH,
    MIN_MESSAGE_LENGTH,
)
from aiuser.common.enums import ScanImageMode
from aiuser.common.utilities import is_embed_valid
from aiuser.messages_list.entry import MessageEntry
from aiuser.random_message_task import RandomMessageTask
from aiuser.response.response_handler import ResponseHandler
from aiuser.settings.base import Settings

logger = logging.getLogger("red.bz_cogs.aiuser")


class AIUser(
    Settings,
    ResponseHandler,
    RandomMessageTask,
    commands.Cog,
    metaclass=CompositeMetaClass,
):
    """Utilize OpenAI to reply to messages and images in approved channels."""

    def __init__(self, bot):
        super().__init__()
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=754070)
        self.openai_client: AsyncOpenAI = None
        # cached options
        self.optin_users: list[int] = []
        self.optout_users: list[int] = []
        self.optindefault: dict[int, bool] = {}
        self.channels_whitelist: dict[int, list[int]] = {}
        self.reply_percent: dict[int, float] = {}
        self.ignore_regex: dict[int, re.Pattern] = {}
        self.override_prompt_start_time: dict[int, datetime] = {}
        self.cached_messages: Cache[int, MessageEntry] = Cache(limit=100)
        self.url_pattern = re.compile(r"(https?://\S+)")

        default_global = {
            "custom_openai_endpoint": None,
            "optout": [],
            "optin": [],
            "ratelimit_reset": datetime(1990, 1, 1, 0, 1).strftime("%Y-%m-%d %H:%M:%S"),
            "max_topic_length": 200,
            "max_prompt_length": 200,
        }

        default_guild = {
            "optin_by_default": False,
            "optin_disable_embed": False,
            "reply_percent": DEFAULT_REPLY_PERCENT,
            "messages_backread": 10,
            "messages_backread_seconds": 60 * 120,
            "reply_to_mentions_replies": False,
            "scan_images": False,
            "scan_images_mode": ScanImageMode.AI_HORDE.value,
            "max_image_size": 2 * (1024 * 1024),
            "model": "gpt-3.5-turbo",
            "custom_text_prompt": None,
            "channels_whitelist": [],
            "public_forget": False,
            "ignore_regex": None,
            "removelist_regexes": DEFAULT_REMOVE_PATTERNS,
            "parameters": None,
            "weights": None,
            "random_messages_enabled": False,
            "random_messages_percent": 0.012,
            "random_messages_topics": DEFAULT_TOPICS,
            "presets": json.dumps(DEFAULT_PRESETS),
            "image_requests": False,
            "image_requests_endpoint": None,
            "image_requests_parameters": None,
            "image_requests_preprompt": "",
            "image_requests_subject": "woman",
            "image_requests_reduced_llm_calls": False,
        }
        default_member = {
            "custom_text_prompt": None,
        }
        default_channel = {
            "custom_text_prompt": None,
        }

        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)
        self.config.register_channel(**default_channel)
        self.config.register_global(**default_global)

    async def cog_load(self):
        await self.initialize_openai_client()

        self.optin_users = await self.config.optin()
        self.optout_users = await self.config.optout()
        all_config = await self.config.all_guilds()

        for guild_id, config in all_config.items():
            self.optindefault[guild_id] = config["optin_by_default"]
            self.channels_whitelist[guild_id] = config["channels_whitelist"]
            self.reply_percent[guild_id] = config["reply_percent"]
            pattern = config["ignore_regex"]
            self.ignore_regex[guild_id] = re.compile(pattern) if pattern else None

        self.random_message_trigger.start()

    async def cog_unload(self):
        self.random_message_trigger.cancel()

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        for guild in self.bot.guilds:
            member = guild.get_member(user_id)
            if member:
                await self.config.member(member).clear()
                # TODO: remove user messages from cache instead of clearing the whole cache
                self.cached_messages = Cache(limit=100)

    @commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name, _):
        if service_name in ["openai", "openrouter"]:
            await self.initialize_openai_client()

    @app_commands.command(name="chat")
    @app_commands.describe(text="The prompt you want to send to the AI.")
    @app_commands.checks.cooldown(1, 30)
    @app_commands.checks.cooldown(1, 5, key=None)
    async def slash_command(
        self,
        inter: discord.Interaction,
        *,
        text: app_commands.Range[str, MIN_MESSAGE_LENGTH, MAX_MESSAGE_LENGTH],
    ):
        """Talk directly to this bot's AI. Ask it anything you want!"""
        await inter.response.defer()

        ctx = await commands.Context.from_interaction(inter)
        ctx.message.content = text
        if not await self.is_common_valid_reply(ctx):
            return await ctx.send(
                "You're not allowed to use this command here.", ephemeral=True
            )

        rate_limit_reset = datetime.strptime(
            await self.config.ratelimit_reset(), "%Y-%m-%d %H:%M:%S"
        )
        if rate_limit_reset > datetime.now():
            return await ctx.send(
                "The command is currently being ratelimited!", ephemeral=True
            )

        try:
            await self.send_response(ctx)
        except:
            await ctx.send(":warning: Error in generating response!", ephemeral=True)

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        ctx: commands.Context = await self.bot.get_context(message)

        if not await self.is_common_valid_reply(ctx):
            return

        if await self.is_bot_mentioned_or_replied(message):
            pass
        elif random.random() > self.reply_percent.get(
            message.guild.id, DEFAULT_REPLY_PERCENT
        ):
            return

        rate_limit_reset = datetime.strptime(
            await self.config.ratelimit_reset(), "%Y-%m-%d %H:%M:%S"
        )
        if rate_limit_reset > datetime.now():
            logger.debug(
                f"Want to respond but ratelimited until {rate_limit_reset.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            if (
                await self.is_bot_mentioned_or_replied(message)
                or self.reply_percent.get(message.guild.id, DEFAULT_REPLY_PERCENT)
                == 1.0
            ):
                await ctx.react_quietly("💤")
            return

        contains_url = self.url_pattern.search(ctx.message.content)
        if contains_url:
            ctx = await self.wait_for_embed(ctx)

        await self.send_response(ctx)

    async def wait_for_embed(self, ctx: commands.Context):
        """Wait for possible embed to be valid"""
        start_time = asyncio.get_event_loop().time()
        while not is_embed_valid(ctx.message):
            ctx.message = await ctx.channel.fetch_message(ctx.message.id)
            if asyncio.get_event_loop().time() - start_time >= 3:
                break
            await asyncio.sleep(1)
        return ctx

    async def is_common_valid_reply(self, ctx: commands.Context) -> bool:
        """Run some common checks to see if a message is valid for the bot to reply to"""
        if not ctx.guild:
            return False
        if await self.bot.cog_disabled_in_guild(self, ctx.guild):
            return False
        if ctx.author.bot or not self.channels_whitelist.get(ctx.guild.id, []):
            return False
        if not ctx.interaction and (
            isinstance(ctx.channel, discord.Thread)
            and ctx.channel.parent.id not in self.channels_whitelist[ctx.guild.id]
            or ctx.channel.id not in self.channels_whitelist[ctx.guild.id]
        ):
            return False
        if not await self.bot.ignored_channel_or_guild(ctx):
            return False
        if not await self.bot.allowed_by_whitelist_blacklist(ctx.author):
            return False
        if ctx.author.id in self.optout_users:
            return False
        if (
            not self.optindefault.get(ctx.guild.id)
            and ctx.author.id not in self.optin_users
        ):
            return False
        if self.ignore_regex.get(ctx.guild.id) and self.ignore_regex[
            ctx.guild.id
        ].search(ctx.message.content):
            return False

        if not self.openai_client:
            await self.initialize_openai_client(ctx)
        if not self.openai_client:
            return False

        return True

    async def is_bot_mentioned_or_replied(self, message: discord.Message) -> bool:
        if not (await self.config.guild(message.guild).reply_to_mentions_replies()):
            return False
        if self.bot.user in message.mentions:
            return True
        if message.reference and message.reference.message_id:
            reference_message = (
                message.reference.cached_message
                or await message.channel.fetch_message(message.reference.message_id)
            )
            return reference_message.author == self.bot.user
        return False

    async def initialize_openai_client(self, ctx: commands.Context = None):
        base_url = await self.config.custom_openai_endpoint()
        api_type = "openai"
        api_key = None
        headers = None

        if base_url and str(base_url).startswith("https://openrouter.ai/api/v1"):
            api_type = "openrouter"
            api_key = (await self.bot.get_shared_api_tokens(api_type)).get("api_key")
            headers = {
                "HTTP-Referer": "https://github.com/zhaobenny/bz-cogs/tree/main/aiuser",
                "X-Title": "ai user",
            }
        else:
            api_key = (await self.bot.get_shared_api_tokens("openai")).get("api_key")

        if not api_key and ctx:
            error_message = (
                f"{api_type} API key not set for `aiuser`. "
                f"Please set it with `{ctx.clean_prefix}set api {api_type} api_key,API_KEY`"
            )
            await ctx.send(error_message)
            return

        if not api_key:
            logger.error(
                f'{api_type} API key not set for "aiuser" yet! Please set it with: [p]set api {api_type} api_key,API_KEY'
            )
            return

        timeout = 60.0 if base_url else 50.0
        self.openai_client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout, default_headers=headers
        )
