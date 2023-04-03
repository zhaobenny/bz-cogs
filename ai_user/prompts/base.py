import json
from typing import Dict, Optional

from discord import Message, User

from ai_user.prompts.constants import DEFAULT_PROMPT


class Prompt:
    def __init__(self, bot: User, message: Message, config, bot_prompt: str = None):
        self.config = config
        self.bot = bot
        self.message = message

    async def _create_prompt(self, bot_prompt : str) -> Optional[str]:
        raise NotImplementedError(
            "_create_full_prompt() must be implemented in subclasses")

    async def get_prompt(self) -> Optional[str]:
        """
            Returns a list of messages to be used as the prompt for the OpenAI API
        """
        bot_prompt = await self.config.guild(self.message.guild).custom_text_prompt() or DEFAULT_PROMPT
        return await self._create_prompt(bot_prompt)

    async def _get_previous_history(self, limit: int = 10):
        """ Returns a history of messages before current message """

        messages = await self.message.channel.history(limit=limit, before=self.message).flatten()
        messages.reverse()

        history = []
        for i, message in enumerate(messages):
            if i > 0 and abs((messages[i - 1].created_at - message.created_at).total_seconds()) > 1188:
                break
            if Prompt.is_not_valid_message(message):
                continue
            if message.reference:
                await self._handle_historical_reply(history, message)

            history.append(self._format_message(message))

        return history

    async def _handle_historical_reply(self, history, message):
        replied_message = await message.channel.fetch_message(message.reference.message_id)
        if Prompt.is_not_valid_message(replied_message):
            return
        formatted_replied_message = self._format_message(replied_message)
        if not Prompt.is_json_in_list(formatted_replied_message, history):
            history.append(formatted_replied_message)
        else:
            # avoid duplicates that will confuse the model
            history.append(
                {"role": "system", "content": f"The following message is a reply to: {replied_message.author.name} said {replied_message.content}"})

    def _format_message(self, message: Message) -> Dict[str, str]:
        """ Formats a message into a JSON format for OpenAI """
        role = "user" if message.author != self.bot else "assistant"
        content = f"User \"{message.author.name}\" said: {message.content}" if role == "user" else message.content
        return {"role": role, "content": content}

    @staticmethod
    def is_not_valid_message(message: Message) -> bool:
        return len(message.attachments) > 1 or len(message.content.split(" ")) > 300

    @staticmethod
    def is_json_in_list(json_obj, json_list):
        return json.dumps(json_obj, sort_keys=True) in json_list
