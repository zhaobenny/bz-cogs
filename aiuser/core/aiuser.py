import json
import logging
import re
from datetime import datetime

import discord
from openai import AsyncOpenAI
from redbot.core import Config, app_commands, commands
from redbot.core.bot import Red

from aiuser.core.handlers import handle_message, handle_slash_command
from aiuser.dashboard_integration import DashboardIntegration
from aiuser.messages_list.entry import MessageEntry
from aiuser.core.random_message_task import RandomMessageTask
from aiuser.settings.base import Settings
from aiuser.types.abc import CompositeMetaClass
from aiuser.types.enums import ScanImageMode
from aiuser.utils.cache import Cache
from aiuser.utils.constants import (
    DEFAULT_IMAGE_REQUEST_SD_GEN_PROMPT,
    DEFAULT_IMAGE_REQUEST_TRIGGER_SECOND_PERSON_WORDS,
    DEFAULT_IMAGE_REQUEST_TRIGGER_WORDS, DEFAULT_IMAGE_UPLOAD_LIMIT,
    DEFAULT_MIN_MESSAGE_LENGTH, DEFAULT_PRESETS, DEFAULT_RANDOM_PROMPTS,
    DEFAULT_REMOVE_PATTERNS, DEFAULT_REPLY_PERCENT)

from .openai_utils import setup_openai_client

logger = logging.getLogger("red.bz_cogs.aiuser")
logging.getLogger("httpcore").setLevel(logging.WARNING)


class AIUser(
    DashboardIntegration,
    Settings,
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
        await handle_slash_command(self, inter, text)

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        await handle_message(self, message)
