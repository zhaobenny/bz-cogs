import json
from typing import Optional

from discord import Message, User


class Prompt:
    def __init__(self, bot: User, message: Message, bot_prompt: str = None):
        self.bot = bot
        self.message = message
        self.bot_prompt = bot_prompt or self._get_default_bot_prompt()

    def _get_default_bot_prompt(self) -> str:
        raise NotImplementedError("_get_default_bot_prompt() must be implemented in subclasses")

    async def _create_full_prompt(self) -> Optional[str]:
        raise NotImplementedError("_create_full_prompt() must be implemented in subclasses")

    async def get_prompt(self) -> Optional[str]:
        """
            Returns a list of messages to be used as the prompt for the OpenAI API
        """
        return await self._create_full_prompt()

    async def _get_previous_history(self, limit: int = 10):
        """ Returns a history of messages before current message """

        def is_not_valid_message(message: Message):
            return len(message.attachments) > 1 or len(message.content.split(" ")) > 300 or len(message.content) == 0

        def format_message(message: Message):
            if message.author.id == self.bot.id:
                role = "assistant"
                content = f"{message.content}"
            else:
                role = "user"
                content = f"[{message.author.name}]: {message.content}"
            return {"role": role, "content": content}

        def is_json_in_list(json_obj, json_list):
            for item in json_list:
                if json.dumps(item, sort_keys=True) == json.dumps(json_obj, sort_keys=True):
                    return True
            return False

        history = await self.message.channel.history(limit=limit, before=self.message).flatten()
        history.reverse()

        messages = []
        for i, message in enumerate(history):
            if i > 0 and (message.created_at - history[i - 1].created_at).total_seconds() > 1188:
                break
            if is_not_valid_message(message):
                continue
            if message.reference:
                replied_message = await message.channel.fetch_message(message.reference.message_id)
                formatted_replied_message = format_message(replied_message)
                if not is_not_valid_message(replied_message):
                    if not is_json_in_list(formatted_replied_message, messages):
                        messages.append(formatted_replied_message)
                    else:
                        # avoid duplicates that will confuse the model
                        messages.append({"role": "system", "content": f"The following message is a reply to: [{replied_message.author.name}]: {replied_message.content}"})

            messages.append(format_message(message))

        return messages