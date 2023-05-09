import logging
from typing import Optional

from discord import Message

from ai_user.prompts.base import Prompt
from ai_user.prompts.common.messages_item import MessagesItem
from ai_user.prompts.common.messages_system_item import MessagesSystemItem
from ai_user.prompts.common.messages_list import MessagesList
from ai_user.constants import MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH
from ai_user.prompts.common.messages_item import MessagesItem
from ai_user.prompts.common.messages_system_item import MessagesSystemItem
from ai_user.prompts.common.messages_list import MessagesList

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

        messages = MessagesList()
        # prompt.extend(await self._get_previous_history())

        messages.append(MessagesSystemItem(content=f"You are {self.bot.name}. {bot_prompt}"))

        if self.message.reference and not messages.is_id_in_messages(self.message.reference.message_id):
            try:
                replied = await self.message.channel.fetch_message(self.message.reference.message_id)
                messages.append(replied)
            except:
                pass

        messages.append(MessagesItem(message=self.message, bot=self.bot))

        return messages
