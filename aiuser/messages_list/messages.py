import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta

import discord
import tiktoken
from discord import Message
from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.common.constants import DEFAULT_PROMPT, OTHER_MODELS_LIMITS
from aiuser.common.utilities import format_variables
from aiuser.messages_list.converter.converter import MessageConverter
from aiuser.messages_list.entry import MessageEntry
from aiuser.messages_list.opt_view import OptView

logger = logging.getLogger("red.bz_cogs.aiuser")


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

    def __len__(self):
        return len(self.messages)

    def __repr__(self) -> str:
        return json.dumps(self.get_json(), indent=4)

    async def _init(self, prompt=None):
        model = await self.config.guild(self.guild).model()
        self.token_limit = self._get_token_limit(model)
        try:
            self._encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self._encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

        if not prompt:  # jank
            await self.add_msg(self.init_message)

        bot_prompt = prompt or await self._pick_prompt()

        await self.add_system(format_variables(self.ctx, bot_prompt))

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
                or DEFAULT_PROMPT)

    async def add_msg(self, message: Message, index: int = None, force: bool = False):
        if self.tokens > self.token_limit:
            return

        if message.id in self.messages_ids and not force:
            logger.debug(
                f"Skipping duplicate message in {message.guild.name} when creating context"
            )
            return

        if self.ignore_regex and self.ignore_regex.search(message.content):
            return
        if not await self.bot.allowed_by_whitelist_blacklist(message.author):
            return
        if message.author.id in await self.config.optout():
            return
        if (
            (not message.author.id == self.bot.user.id)
            and not message.author.id in await self.config.optin()
            and not await self.config.guild(self.guild).optin_by_default()
        ):
            return

        converted = await self.converter.convert(message)

        if not converted:
            return

        for entry in converted:
            self.messages.insert(index or 0, entry)
            self.messages_ids.add(message.id)
            await self._add_tokens(entry.content)

        # TODO: proper chaining
        if (
            message.reference
            and type(message.reference.resolved) == discord.Message
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
        OPTIN_EMBED_TITLE = ":information_source: AI User Opt-In / Opt-Out"
        limit = await self.config.guild(self.guild).messages_backread()
        max_seconds_gap = await self.config.guild(
            self.guild
        ).messages_backread_seconds()
        start_time: datetime = (
            self.start_time + timedelta(seconds=1) if self.start_time else None
        )

        past_messages = [
            message
            async for message in self.init_message.channel.history(
                limit=limit + 1,
                before=self.init_message,
                after=start_time,
                oldest_first=False,
            )
        ]

        if (past_messages and not (await self._is_valid_time_gap(self.init_message, past_messages[0], max_seconds_gap))):
            return

        users = set()
        for message in past_messages:
            if await self.config.guild(self.guild).optin_by_default():
                break
            if (
                (not message.author.bot)
                and (message.author.id not in await self.config.optin())
                and (message.author.id not in await self.config.optout())
            ):
                users.add(message.author)

        for i in range(len(past_messages) - 1):
            if self.tokens > self.token_limit:
                return logger.debug(
                    f"{self.tokens} tokens used - nearing limit, stopping context creation for message {self.init_message.id}"
                )
            if (past_messages[i].author.id == self.bot.user.id) and (past_messages[i].embeds and past_messages[i].embeds[0].title == OPTIN_EMBED_TITLE):
                continue
            if await self._is_valid_time_gap(past_messages[i], past_messages[i + 1], max_seconds_gap):
                await self.add_msg(past_messages[i])
            else:
                await self.add_msg(past_messages[i])
                break

        if users and not (await self.config.guild(self.guild).optin_disable_embed()):
            users = ", ".join([user.mention for user in users])
            embed = discord.Embed(
                title=OPTIN_EMBED_TITLE,
                color=await self.bot.get_embed_color(message),
            )
            view = OptView(self.config)
            embed.description = f"Hey there, looks like {users} have not opted in or out of AI User! \n Please opt in/out of sending your messages/images to OpenAI/external party. \n This embed will stop showing up if all users chatting have opted in or out."
            await message.channel.send(embed=embed, view=view)

    def get_json(self):
        result = []
        for message in self.messages:
            result.append(asdict(message))
        return result

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
        model = model.split("/")[-1]
        if model in OTHER_MODELS_LIMITS:
            limit = OTHER_MODELS_LIMITS.get(model, limit)
        return limit

    @staticmethod
    async def _is_valid_time_gap(message: discord.Message, next_message: discord.Message, max_seconds_gap: int) -> bool:
        seconds_diff = abs(message.created_at - next_message.created_at).total_seconds()
        if seconds_diff > max_seconds_gap:
            return False
        return True
