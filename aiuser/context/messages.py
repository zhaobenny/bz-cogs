import json
import logging
from typing import List

import discord
import tiktoken
from discord import Message
from redbot.core import commands
from redbot.core.data_manager import cog_data_path

from aiuser.config.defaults import DEFAULT_PROMPT
from aiuser.config.models import OTHER_MODELS_LIMITS
from aiuser.context.consent.manager import ConsentManager
from aiuser.context.converter.converter import MessageConverter
from aiuser.context.entry import MessageEntry
from aiuser.context.history.manager import HistoryManager
from aiuser.context.memory.retriever import MemoryRetriever
from aiuser.types.abc import MixinMeta
from aiuser.types.enums import ScanImageMode
from aiuser.utils.utilities import format_variables

logger = logging.getLogger("red.bz_cogs.aiuser")

OPTIN_EMBED_TITLE = ":information_source: AI User Opt-In / Opt-Out"


async def create_messages_list(
    cog: MixinMeta, ctx: commands.Context, prompt: str = None, history: bool = True
):
    """to manage messages in ChatML format"""
    thread = MessagesList(cog, ctx)
    await thread._init(prompt=prompt)
    if history:
        await thread.add_history()
    return thread


class MessagesList:
    def __init__(
        self,
        cog: MixinMeta,
        ctx: commands.Context,
    ):
        self.bot = cog.bot
        self.config = cog.config
        self.ctx = ctx
        self.init_message = ctx.message
        self.guild = ctx.guild
        self.ignore_regex = cog.ignore_regex.get(self.guild.id, None)
        self.start_time = cog.override_prompt_start_time.get(
            self.guild.id)
        self.messages: List[MessageEntry] = []
        self.messages_ids = set()
        self.tokens = 0
        self.model = None
        self.can_reply = True
        self.converter = MessageConverter(cog, ctx)
        self.consent_manager = ConsentManager(self.config, self.bot, self.guild)
        self.memory_retriever = MemoryRetriever(cog_data_path(cog))
        self.history_manager = HistoryManager(self)

    def __len__(self):
        return len(self.messages)

    def __repr__(self) -> str:
        return json.dumps(self.get_json(), indent=4)

    async def _init(self, prompt=None):
        self.model = await self.config.guild(self.guild).model()
        self.token_limit = await self.config.guild(self.guild).custom_model_tokens_limit() or self._get_token_limit(self.model)
        try:
            self._encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            self._encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

        if not prompt:  # jank
            await self.add_msg(self.init_message)

        bot_prompt = prompt or await self._pick_prompt()

        await self.add_system(await format_variables(self.ctx, bot_prompt))

        if await self._check_if_inital_img():
            self.model = await self.config.guild(self.guild).scan_images_model()

    async def _check_if_inital_img(self) -> bool:
        if (
            self.ctx.interaction
            or not await self.config.guild(self.guild).scan_images()
            or await self.config.guild(self.guild).scan_images_mode() != ScanImageMode.LLM.value
        ):
            return False
        if self.init_message.attachments and self.init_message.attachments[0].content_type.startswith('image/'):
            return True
        elif self.init_message.reference:
            ref = self.init_message.reference
            replied = ref.cached_message or await self.bot.get_channel(ref.channel_id).fetch_message(ref.message_id)
            return replied.attachments and replied.attachments[0].content_type.startswith('image/')
        else:
            return False

    async def _pick_prompt(self):
        author = self.init_message.author
        role_prompt = None

        for role in author.roles:
            if role.id in (await self.config.all_roles()):
                role_prompt = await self.config.role(role).custom_text_prompt()
                break

        return (await self.config.member(self.init_message.author).custom_text_prompt()
                or role_prompt
                or await self.config.channel(self.init_message.channel).custom_text_prompt()
                or await self.config.guild(self.guild).custom_text_prompt()
                or await self.config.custom_text_prompt()
                or DEFAULT_PROMPT)

    async def check_if_add(self, message: Message, force: bool = False):
        if self.tokens > self.token_limit:
            return False

        if message.id in self.messages_ids and not force:
            logger.debug(
                f"Skipping duplicate message in {message.guild.name} when creating context"
            )
            return False

        if self.ignore_regex and self.ignore_regex.search(message.content):
            return False
        if not await self.bot.allowed_by_whitelist_blacklist(message.author):
            return False
        if message.author.id in await self.config.optout():
            return False
        if not await self.consent_manager.is_user_allowed(message.author):
            return False

        return True

    async def add_msg(self, message: Message, index: int = None, force: bool = False):
        if not await self.check_if_add(message, force):
            return

        converted = await self.converter.convert(message)

        if not converted:
            return

        for entry in converted:
            if self.tokens > self.token_limit:
                return

            self.messages.insert(index or 0, entry)
            self.messages_ids.add(message.id)

            if isinstance(entry.content, list):
                for item in entry.content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text":
                        await self._add_tokens(item.get("text"))
                    elif item.get("type") == "image_url":
                        self.tokens += 255  # TODO: calculate actual image token cost
            else:
                await self._add_tokens(entry.content)

        # TODO: proper reply chaining
        if message.reference and isinstance(message.reference.resolved, discord.Message) and message.author.id != self.bot.user.id:
            await self.add_msg(message.reference.resolved, index=0)

    async def add_system(self, content: str, index: int = None):
        if self.tokens > self.token_limit:
            return
        entry = MessageEntry("system", content)
        self.messages.insert(index or 0, entry)
        await self._add_tokens(content)

    async def add_assistant(self, content: str = "", index: int = None, tool_calls: list = []):
        if self.tokens > self.token_limit:
            return
        entry = MessageEntry("assistant", content, tool_calls=tool_calls)
        self.messages.insert(index or 0, entry)
        await self._add_tokens(content)

    async def add_tool_result(self, content: str,  tool_call_id: int, index: int = None):
        if self.tokens > self.token_limit:
            return
        entry = MessageEntry("tool", content, tool_call_id=tool_call_id)
        self.messages.insert(index or 0, entry)
        await self._add_tokens(content)

    async def add_history(self):
        await self.insert_relevant_memory()
        await self.history_manager.add_history()

    async def insert_relevant_memory(self):
        relevant_memory = await self.memory_retriever.fetch_relevant(self.init_message.content)
        if relevant_memory:
            await self.add_system(relevant_memory, index=len(self.messages_ids))

    def get_json(self):
        return [
            {
                "role": message.role,
                "content": message.content,
                **({"tool_calls": message.tool_calls} if message.tool_calls else {}),
                **({"tool_call_id": message.tool_call_id} if hasattr(message, 'tool_call_id') and message.tool_call_id else {})
            }
            for message in self.messages
        ]

    async def _add_tokens(self, content):
        if not self._encoding:
            await self._initialize_encoding()
        content = str(content)
        tokens = self._encoding.encode(content, disallowed_special=())
        self.tokens += len(tokens)

    @staticmethod
    def _get_token_limit(model) -> int:
        limit = 7000
        
        if 'gemini-2' in model or 'gpt-4.1' in model or 'llama-4.1' in model:
            limit = 1000000
        if 'gpt-5' in model:
            limit = 390000
        if "gpt-4o" in model or "llama-3.1" in model or "llama-3.2" in model or 'grok-3' in model:
            limit = 123000
        if "100k" in model or "claude" in model:
            limit = 98000
        if "16k" in model:
            limit = 15000
        if "32k" in model:
            limit = 31000

        model = model.split("/")[-1].split(":")[0]
        if model in OTHER_MODELS_LIMITS:
            limit = OTHER_MODELS_LIMITS.get(model, limit)

        return limit

    @staticmethod
    async def _is_valid_time_gap(message: discord.Message, next_message: discord.Message, max_seconds_gap: int) -> bool:
        seconds_diff = abs(message.created_at - next_message.created_at).total_seconds()
        if seconds_diff > max_seconds_gap:
            return False
        return True
