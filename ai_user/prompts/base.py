from discord import Member, Message
from redbot.core import Config
from typing import Optional

from ai_user.common.constants import MAX_HISTORY_MESSAGE_LENGTH
from ai_user.common.types import ContextOptions
from ai_user.prompts.common.helpers import format_text_content
from ai_user.prompts.common.messages_list import MessagesList
from ai_user.prompts.presets import DEFAULT_PROMPT


class Prompt:
    def __init__(self, cog: MixinMeta, message):
        self.config: Config = config
        self.bot: Member = message.guild.me
        self.message: Message = message
        self.context_options = context_options
        self.messages: Optional[MessagesList] = None
        self.cog_data_path = cog_data_path(cog)

    async def _handle_message(self) -> Optional[MessagesList]:
        raise NotImplementedError("_handle_message() must be implemented in subclasses")

    async def get_list(self) -> Optional[MessagesList]:
        """
            Returns a list of messages to be used as the prompt for the OpenAI API
        """

        bot_prompt = await self.config.member(self.message.author).custom_text_prompt() \
            or await self.config.channel(self.message.channel).custom_text_prompt() \
            or await self.config.guild(self.message.guild).custom_text_prompt() \
            or DEFAULT_PROMPT

        self.messages = MessagesList(self.bot, self.config, self.message)

        await self.messages.add_system(f"You are {self.bot.display_name}. {bot_prompt}")

        if self.message.reference:
            try:
                replied = self.message.reference.cached_message or await self.message.channel.fetch_message(self.message.reference.message_id)
                if self._is_valid_reply(replied):
                    await self.messages.add_msg(format_text_content(replied), replied)
            except:
                pass

        self.messages = await self._handle_message()
        if self.messages is None:
            return None

        await self.messages.create_context(self.context_options)
        return self.messages

    @staticmethod
    def _is_valid_reply(message: Message) -> bool:
        return message.content and len(message.attachments) < 1 and len(message.content.split(" ")) < MAX_HISTORY_MESSAGE_LENGTH
