from datetime import datetime, timedelta
from typing import Dict, Optional
from discord import Member, Message
from redbot.core import Config

from ai_user.prompts.presets import DEFAULT_PROMPT
from ai_user.constants import MAX_MESSAGE_LENGTH


class Prompt:
    def __init__(self, message: Message, config: Config, start_time: datetime):
        self.config: Config = config
        self.bot: Member = message.guild.me
        self.message: Message = message
        self.start_time: datetime = start_time + \
            timedelta(seconds=1) if start_time else None

    async def _create_prompt(self, bot_prompt: str) -> Optional[str]:
        raise NotImplementedError(
            "_create_prompt() must be implemented in subclasses")

    async def get_prompt(self) -> Optional[str]:
        """
            Returns a list of messages to be used as the prompt for the OpenAI API
        """

        bot_prompt = await self.config.member(self.message.author).custom_text_prompt() \
            or await self.config.channel(self.message.channel).custom_text_prompt() \
            or await self.config.guild(self.message.guild).custom_text_prompt() \
            or DEFAULT_PROMPT
        full_prompt = await self._create_prompt(bot_prompt)
        if full_prompt is None:
            return None
        return full_prompt

    @staticmethod
    def is_not_valid_message(message: Message) -> bool:
        return (not message.content) or len(message.attachments) >= 1 or len(message.content.split(" ")) > MAX_MESSAGE_LENGTH
