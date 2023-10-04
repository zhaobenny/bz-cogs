from typing import Optional

from discord import Message
from redbot.core import Config
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from aiuser.abc import MixinMeta
from aiuser.prompts.common.messagethread import MessageThread
from aiuser.common.constants import DEFAULT_PROMPT


class Prompt:
    def __init__(self, cog: MixinMeta, message):
        self.config: Config = cog.config
        self.bot: Red = cog.bot
        self.message: Message = message
        self.cog_data_path = cog_data_path(cog)
        start_time = cog.override_prompt_start_time.get(self.message.guild.id)
        self.cached_messages = cog.cached_messages
        self.messages: Optional[MessageThread] = MessageThread(self.bot, self.config, self.message, cached_messages=self.cached_messages,
                                                               ignore_regex=cog.ignore_regex.get(self.message.guild.id), start_time=start_time)

    async def _handle_message(self) -> Optional[MessageThread]:
        raise NotImplementedError("_handle_message() must be implemented in subclasses")

    async def get_list(self) -> Optional[MessageThread]:
        """
            Returns a thread of messages to be used as the prompt for the OpenAI API
        """

        bot_prompt = await self.config.member(self.message.author).custom_text_prompt() \
            or await self.config.channel(self.message.channel).custom_text_prompt() \
            or await self.config.guild(self.message.guild).custom_text_prompt() \
            or DEFAULT_PROMPT

        await self.messages.add_system(f"You are {self.message.guild.me.nick or self.bot.user.display_name}. {bot_prompt}")

        if self.message.reference:
            try:
                replied = self.message.reference.cached_message or await self.message.channel.fetch_message(self.message.reference.message_id)
                await self.messages.add_contextual_message(replied)
            except:
                pass

        self.messages = await self._handle_message()
        if self.messages is None:
            return None

        await self.messages.create_context()
        return self.messages
