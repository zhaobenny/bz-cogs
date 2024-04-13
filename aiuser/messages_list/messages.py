import json
import logging
import random
from dataclasses import asdict
from datetime import datetime, timedelta

import discord
import tiktoken
from discord import Message
from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.common.constants import DEFAULT_PROMPT, OTHER_MODELS_LIMITS
from aiuser.common.enums import ScanImageMode
from aiuser.common.utilities import format_variables
from aiuser.messages_list.converter.converter import MessageConverter
from aiuser.messages_list.entry import MessageEntry
from aiuser.messages_list.opt_view import OptView

logger = logging.getLogger("red.bz_cogs.aiuser")

OPTIN_EMBED_TITLE = ":information_source: AI User Opt-In / Opt-Out"


async def create_messages_list(
    cog: MixinMeta, ctx: commands.Context, prompt: str = None
):
    """to manage messages in ChatML format"""
    thread = MessagesList(cog, ctx)
    await thread._init(prompt=prompt)
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
        self.converter = MessageConverter(cog, ctx)
        self.init_message = ctx.message
        self.guild = ctx.guild
        self.ignore_regex = cog.ignore_regex.get(self.guild.id, None)
        self.start_time = cog.override_prompt_start_time.get(
            self.guild.id)
        self.messages = []
        self.messages_ids = set()
        self.tokens = 0
        self.model = None
        self.can_reply = True

    def __len__(self):
        return len(self.messages)

    def __repr__(self) -> str:
        return json.dumps(self.get_json(), indent=4)

    async def _init(self, prompt=None):
        self.model = await self.config.guild(self.guild).model()
        self.token_limit = self._get_token_limit(self.model)
        try:
            self._encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            self._encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

        if not prompt:  # jank
            await self.add_msg(self.init_message)

        bot_prompt = prompt or await self._pick_prompt()

        await self.add_system(format_variables(self.ctx, bot_prompt))

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
        if (
            (not message.author.id == self.bot.user.id)
            and not message.author.id in await self.config.optin()
            and not await self.config.guild(self.guild).optin_by_default()
        ):
            return False

        return True

    async def add_msg(self, message: Message, index: int = None, force: bool = False):
        if not await self.check_if_add(message, force):
            return

        converted = await self.converter.convert(message)

        if not converted:
            return

        for entry in converted:
            self.messages.insert(index or 0, entry)
            self.messages_ids.add(message.id)
            for item in entry.content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        await self._add_tokens(item.get("text"))
                else:
                    await self._add_tokens(item)

        # TODO: proper reply chaining
        if (
            message.reference
            and isinstance(message.reference.resolved, discord.Message)
            and message.author.id != self.bot.user.id
        ):
            await self.add_msg(message.reference.resolved, index=0)

    async def add_system(self, content: str, index: int = None):
        if self.tokens > self.token_limit:
            return
        entry = MessageEntry("system", content)
        self.messages.insert(index or 0, entry)
        await self._add_tokens(content)

    async def add_history(self):
        limit = await self.config.guild(self.guild).messages_backread()
        max_seconds_gap = await self.config.guild(self.guild).messages_backread_seconds()
        start_time: datetime = (
            self.start_time + timedelta(seconds=1) if self.start_time else None
        )

        past_messages = await self._get_past_messages(limit, start_time)
        if not past_messages:
            return

        if not await self._is_valid_time_gap(self.init_message, past_messages[0], max_seconds_gap):
            return

        users = await self._get_unopted_users(past_messages[:10])

        await self._process_past_messages(past_messages, max_seconds_gap)

        if users and not await self.config.guild(self.guild).optin_disable_embed():
            if (random.random() <= 0.33) or (len(users) > 3):
                await self._send_optin_embed(users)

    async def _get_past_messages(self, limit, start_time):
        return [
            message
            async for message in self.init_message.channel.history(
                limit=limit + 1,
                before=self.init_message,
                after=start_time,
                oldest_first=False,
            )
        ]

    async def _get_unopted_users(self, messages):
        users = set()

        if await self.config.guild(self.guild).optin_by_default():
            return users

        for message in messages:
            if (
                (not message.author.bot)
                and (message.author.id not in await self.config.optin())
                and (message.author.id not in await self.config.optout())
            ):
                users.add(message.author)

        return users

    async def _process_past_messages(self, past_messages, max_seconds_gap):
        for i in range(len(past_messages) - 1):
            if self.tokens > self.token_limit:
                return logger.debug(f"{self.tokens} tokens used - nearing limit, stopping context creation for message {self.init_message.id}")
            if (past_messages[i].author.id == self.bot.user.id) and (past_messages[i].embeds and past_messages[i].embeds[0].title == OPTIN_EMBED_TITLE):
                continue
            if await self._is_valid_time_gap(past_messages[i], past_messages[i + 1], max_seconds_gap):
                await self.add_msg(past_messages[i])
            else:
                await self.add_msg(past_messages[i])
                break

    async def _send_optin_embed(self, users):
        users = ", ".join([user.mention for user in users])
        embed = discord.Embed(
            title=OPTIN_EMBED_TITLE,
            color=await self.bot.get_embed_color(self.init_message),
        )
        view = OptView(self.config)
        embed.description = f"{users}\nPlease select whether you want to opt into your Discord messages being sent to OpenAI or an external party, as part of this bot.\nThis message will disappear if all users in the chat have made a choice."
        await self.init_message.channel.send(embed=embed, view=view)

    def get_json(self):
        return [asdict(message) for message in self.messages]

    async def _add_tokens(self, content):
        if not self._encoding:
            await self._initialize_encoding()
        content = str(content)
        tokens = self._encoding.encode(content, disallowed_special=())
        self.tokens += len(tokens)

    @staticmethod
    def _get_token_limit(model) -> int:
        limit = 3000
        if "gpt-3.5" in model:
            limit = 3000
        if "gpt-4" in model:
            limit = 7000
        if "8k" in model:
            limit = 7000
        if "16k" in model:
            limit = 15000
        if "32k" in model:
            limit = 31000
        if "100k" in model or "claude" in model:
            limit = 99000
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
