import logging
from typing import Optional

from discord import Message

from ai_user.prompts.base import Prompt
from ai_user.constants import MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH

logger = logging.getLogger("red.bz_cogs.ai_user")


class TextPrompt(Prompt):
    def __init__(self, message: Message, config, start_time):
        super().__init__(message, config, start_time)

    @staticmethod
    def _is_acceptable_message(message: Message) -> bool:
        if not message.content:
            logger.debug(f"Skipping empty message in {message.guild.name}")
            return False

        if len(message.content) < MIN_MESSAGE_LENGTH:
            logger.debug(
                f"Skipping short message: {message.content} in {message.guild.name}")
            return False

        if len(message.content.split()) > MAX_MESSAGE_LENGTH:
            logger.debug(
                f"Skipping long message: {message.content} in {message.guild.name}")
            return False

        return True

    async def _create_prompt(self, bot_prompt) -> Optional[list[dict[str, str]]]:
        if not self._is_acceptable_message(self.message):
            return None

        prompt = []
        prompt.extend(await self._get_previous_history())

        prompt.append(
            {"role": "system",
                "content": f"You are {self.bot.name}. {bot_prompt}"},
        )

        if self.message.reference and not self.is_id_in_messages(self.message.reference.message_id, prompt):
            try:
                replied = await self.message.channel.fetch_message(self.message.reference.message_id)
                formattted_replied = self._format_message(replied)
                prompt.append(formattted_replied)
            except:
                pass

        prompt.append(self._format_message(self.message))

        return prompt
