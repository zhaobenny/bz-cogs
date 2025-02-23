import asyncio
import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone

import discord
from openai import AsyncOpenAI
from redbot.core import Config, app_commands, commands
from redbot.core.bot import Red

from aiuser.core.validators import is_bot_mentioned_or_replied, is_common_valid_reply
from aiuser.types.abc import CompositeMetaClass
from aiuser.dashboard_integration import DashboardIntegration
from aiuser.messages_list.entry import MessageEntry
from aiuser.random_message_task import RandomMessageTask
from aiuser.response.response_handler import ResponseHandler
from aiuser.settings.base import Settings
from aiuser.utils.cache import Cache
from aiuser.utils.constants import (
    DEFAULT_IMAGE_REQUEST_SD_GEN_PROMPT,
    DEFAULT_IMAGE_REQUEST_TRIGGER_SECOND_PERSON_WORDS,
    DEFAULT_IMAGE_REQUEST_TRIGGER_WORDS, DEFAULT_IMAGE_UPLOAD_LIMIT,
    DEFAULT_MIN_MESSAGE_LENGTH, DEFAULT_PRESETS, DEFAULT_RANDOM_PROMPTS,
    DEFAULT_REMOVE_PATTERNS, DEFAULT_REPLY_PERCENT,
    SINGULAR_MENTION_PATTERN, URL_PATTERN)
from aiuser.types.enums import ScanImageMode
from .openai_utils import setup_openai_client

from aiuser.utils.utilities import is_embed_valid

logger = logging.getLogger("red.bz_cogs.aiuser")
logging.getLogger("httpcore").setLevel(logging.WARNING)


class AIUser(
    DashboardIntegration,
    Settings,
    ResponseHandler,
    RandomMessageTask,
    commands.Cog,
    metaclass=CompositeMetaClass,
):
    """
        Human-like Discord interactions powered by OpenAI (or compatible endpoints) for messages (and images).
    """

    def __init__(self, bot):
        super().__init__()
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=754070)
        self.openai_client: AsyncOpenAI = None
        # cached options
        self.optindefault: dict[int, bool] = {}
        self.channels_whitelist: dict[int, list[int]] = {}
        self.ignore_regex: dict[int, re.Pattern] = {}
        self.override_prompt_start_time: dict[int, datetime] = {}
        self.cached_messages: Cache[int, MessageEntry] = Cache(limit=100)

        default_global = {
            "custom_openai_endpoint": None,
            "openai_endpoint_request_timeout": 60,
            "optout": [],
            "optin": [],
            "ratelimit_reset": datetime(1990, 1, 1, 0, 1).strftime("%Y-%m-%d %H:%M:%S"),
            "max_random_prompt_length": 200,
            "max_prompt_length": 200,
            "custom_text_prompt": None,
        }

        default_guild = {
            "optin_by_default": False,
            "optin_disable_embed": False,
            "reply_percent": DEFAULT_REPLY_PERCENT,
            "messages_backread": 10,
            "messages_backread_seconds": 60 * 120,
            "messages_min_length": DEFAULT_MIN_MESSAGE_LENGTH,
            "reply_to_mentions_replies": True,
            "scan_images": False,
            "scan_images_mode": ScanImageMode.AI_HORDE.value,
            "scan_images_model": "gpt-4o",
            "max_image_size": DEFAULT_IMAGE_UPLOAD_LIMIT,
            "model": "gpt-3.5-turbo",
            "custom_text_prompt": None,
            "channels_whitelist": [],
            "roles_whitelist": [],
            "members_whitelist": [],
            "public_forget": False,
            "ignore_regex": None,
            "removelist_regexes": DEFAULT_REMOVE_PATTERNS,
            "parameters": None,
            "weights": None,
            "random_messages_enabled": False,
            "random_messages_percent": 0.012,
            "random_messages_prompts": DEFAULT_RANDOM_PROMPTS,
            "presets": json.dumps(DEFAULT_PRESETS),
            "image_requests": False,
            "image_requests_endpoint": "dall-e-2",
            "image_requests_parameters": None,
            "image_requests_sd_gen_prompt": DEFAULT_IMAGE_REQUEST_SD_GEN_PROMPT,
            "image_requests_preprompt": "",
            "image_requests_subject": "woman",
            "image_requests_reduced_llm_calls": False,
            "image_requests_trigger_words": DEFAULT_IMAGE_REQUEST_TRIGGER_WORDS,
            "image_requests_second_person_trigger_words": DEFAULT_IMAGE_REQUEST_TRIGGER_SECOND_PERSON_WORDS,
            "function_calling": False,
            "function_calling_functions": [],
            "function_calling_default_location": [49.24966, -123.11934],
            "conversation_reply_percent": 0,
            "conversation_reply_time": 20,
            "custom_model_tokens_limit": None,
        }
        default_channel = {
            "custom_text_prompt": None,
            "reply_percent": None
        }
        default_role = {
            "custom_text_prompt": None,
            "reply_percent": None
        }
        default_member = {
            "custom_text_prompt": None,
            "reply_percent": None
        }

        self.config.register_member(**default_member)
        self.config.register_role(**default_role)
        self.config.register_channel(**default_channel)
        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

    async def cog_load(self):
        self.openai_client = await setup_openai_client(self.bot, self.config)

        all_config = await self.config.all_guilds()

        for guild_id, config in all_config.items():
            self.optindefault[guild_id] = config["optin_by_default"]
            self.channels_whitelist[guild_id] = config["channels_whitelist"]
            pattern = config["ignore_regex"]

            self.ignore_regex[guild_id] = re.compile(pattern) if pattern else None

        if logger.isEnabledFor(logging.DEBUG):
            # for development
            test_guild = 744802856074346556
            self.override_prompt_start_time[test_guild] = datetime.now()

        self.random_message_trigger.start()

    async def cog_unload(self):
        if self.openai_client:
            await self.openai_client.close()
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
            self.openai_client = await setup_openai_client(self.bot, self.config)

    @app_commands.command(name="chat")
    @app_commands.describe(text="The prompt you want to send to the AI.")
    @app_commands.checks.cooldown(1, 30)
    @app_commands.checks.cooldown(1, 5, key=None)
    async def slash_command(
        self,
        inter: discord.Interaction,
        *,
        text: app_commands.Range[str, 1, 2000],
    ):
        """Talk directly to this bot's AI. Ask it anything you want!"""
        await inter.response.defer()

        ctx = await commands.Context.from_interaction(inter)
        ctx.message.content = text

        if not await self.is_common_valid_reply(ctx):
            return await ctx.send(
                "You're not allowed to use this command here.", ephemeral=True
            )
        elif await self.get_percentage(ctx) == 1.0:
            pass
        elif not (await self.config.guild(ctx.guild).reply_to_mentions_replies()):
            return await ctx.send("This command is not enabled.", ephemeral=True)

        rate_limit_reset = datetime.strptime(
            await self.config.ratelimit_reset(), "%Y-%m-%d %H:%M:%S"
        )
        if rate_limit_reset > datetime.now():
            return await ctx.send(
                "The command is currently being ratelimited!", ephemeral=True
            )

        try:
            await self.create_response(ctx)
        except Exception:
            await ctx.send(":warning: Error in generating response!", ephemeral=True)

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        ctx: commands.Context = await self.bot.get_context(message)

        if not await is_common_valid_reply(self, ctx):
            return

        if await self.is_bot_mentioned_or_replied(message) or await self.is_in_conversation(ctx):
            pass
        elif random.random() > await self.get_percentage(ctx):
            return

        rate_limit_reset = datetime.strptime(await self.config.ratelimit_reset(), "%Y-%m-%d %H:%M:%S")
        if rate_limit_reset > datetime.now():
            logger.debug(f"Want to respond but ratelimited until {rate_limit_reset.strftime('%Y-%m-%d %H:%M:%S')}")
            if (
                await is_bot_mentioned_or_replied(self, message)
                or await self.get_percentage(ctx) == 1.0
            ):
                await ctx.react_quietly("💤", message="`aiuser` is ratedlimited")
            return

        if URL_PATTERN.search(ctx.message.content):
            ctx = await self.wait_for_embed(ctx)

        await self.create_response(ctx)

    async def get_percentage(self, ctx: commands.Context) -> bool:
        role_percent = None
        author = ctx.author

        for role in author.roles:
            if role.id in (await self.config.all_roles()):
                role_percent = await self.config.role(role).reply_percent()
                break

        percentage = await self.config.member(author).reply_percent()
        if percentage == None:
            percentage = role_percent
        if percentage == None:
            percentage = await self.config.channel(ctx.channel).reply_percent()
        if percentage == None:
            percentage = await self.config.guild(ctx.guild).reply_percent()
        if percentage == None:
            percentage = DEFAULT_REPLY_PERCENT
        return percentage

    async def is_in_conversation(self, ctx: commands.Context) -> bool:
        reply_percent = await self.config.guild(ctx.guild).conversation_reply_percent()
        reply_time_seconds = await self.config.guild(ctx.guild).conversation_reply_time()

        if reply_percent == 0 or reply_time_seconds == 0:
            return False

        cutoff_time = datetime.now(tz=timezone.utc) - timedelta(seconds=reply_time_seconds)

        async for message in ctx.channel.history(limit=10):
            if message.author.id == self.bot.user.id and len(message.embeds) == 0 and message.created_at > cutoff_time:
                return random.random() < reply_percent

        return False

    async def wait_for_embed(self, ctx: commands.Context):
        """Wait for possible embed to be valid"""
        start_time = asyncio.get_event_loop().time()
        while not is_embed_valid(ctx.message):
            ctx.message = await ctx.channel.fetch_message(ctx.message.id)
            if asyncio.get_event_loop().time() - start_time >= 3:
                break
            await asyncio.sleep(1)
        return ctx