import json
from typing import Dict, Optional

from discord import Message, User


class Prompt:
    def __init__(self, bot: User, message: Message, bot_prompt: str = None):
        self.bot = bot
        self.message = message
        self.bot_prompt = bot_prompt or self._get_default_bot_prompt()

    def _get_default_bot_prompt(self) -> str:
        raise NotImplementedError(
            "_get_default_bot_prompt() must be implemented in subclasses")

    async def _create_full_prompt(self) -> Optional[str]:
        raise NotImplementedError(
            "_create_full_prompt() must be implemented in subclasses")

    async def get_prompt(self) -> Optional[str]:
        """
            Returns a list of messages to be used as the prompt for the OpenAI API
        """
        return await self._create_full_prompt()

    def _is_not_valid_message(self, message: Message) -> bool:
        return len(message.attachments) > 1 or len(message.content.split(" ")) > 300 or len(message.content) == 0

    def _format_message(self, message: Message) -> Dict[str, str]:
        """ Formats a message into a JSON with the role and content """
        role = "user" if message.author != self.bot else "assistant"
        content = f"[{message.author.name}]: {message.content}" if role == "user" else message.content
        return {"role": role, "content": content}

    def _is_json_in_list(json_obj, json_list):
        return json.dumps(json_obj, sort_keys=True) in json_list

    async def _get_previous_history(self, limit: int = 10):
        """ Returns a history of messages before current message """

        history = await self.message.channel.history(limit=limit, before=self.message).flatten()
        history.reverse()

        messages = []
        for i, message in enumerate(history):
            if i > 0 and (message.created_at - history[i - 1].created_at).total_seconds() > 1188:
                break
            if self._is_not_valid_message(message):
                continue
            if message.reference:
                replied_message = await message.channel.fetch_message(message.reference.message_id)
                formatted_replied_message = self._format_message(replied_message)
                if not self._is_not_valid_message(replied_message):
                    if not self._is_json_in_list(formatted_replied_message, messages):
                        messages.append(formatted_replied_message)
                    else:
                        # avoid duplicates that will confuse the model
                        messages.append(
                            {"role": "system", "content": f"The following message is a reply to: [{replied_message.author.name}]: {replied_message.content}"})

            messages.append(self._format_message(message))

        return messages
