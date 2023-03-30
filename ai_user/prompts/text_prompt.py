import logging
from typing import Optional

from discord import Message, User

from ai_user.prompts.base import Prompt
from ai_user.prompts.constants import DEFAULT_TEXT_PROMPT

logger = logging.getLogger("red.bz_cogs.ai_user")


class TextPrompt(Prompt):
    def __init__(self, bot: User, message: Message, bot_prompt: str = None):
        super().__init__(bot, message, bot_prompt)

    def _get_default_bot_prompt(self) -> str:
        return DEFAULT_TEXT_PROMPT

    def _is_acceptable_message(self, message: Message) -> bool:
        if not message.content:
            logger.debug(f"Skipping empty message in {message.guild.name}")
            return False

        if len(message.content) < 5:
            logger.debug(
                f"Skipping short message: {message.content} in {message.guild.name}")
            return False

        if len(message.content.split()) > 300:
            logger.debug(
                f"Skipping long message: {message.content} in {message.guild.name}")
            return False

        return True

    async def _create_full_prompt(self) -> Optional[str]:
        if not self._is_acceptable_message(self.message):
            return None

        prompt = []
        prompt.extend(await self._get_previous_history())

        prompt.append(
            {"role": "system",
                "content": f"You are {self.bot.name}. Do not include '{self.bot.name}' in the response. Do not react to the username before the ':'. You are in a Discord text channel. {self.bot_prompt}"},
        )

        if self.message.reference:
            replied = await self.message.channel.fetch_message(self.message.reference.message_id)
            formattted_replied = self._format_message(replied)
            prompt.append(formattted_replied)

        prompt.append(self._format_message(self.message))

        return prompt
