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
        self.remove_id_field_in_prompt(full_prompt)
        return full_prompt

    async def _get_previous_history(self):
        """ Returns a history of messages before current message """
        limit = await self.config.guild(self.message.guild).messages_backread()
        messages = [message async for message in self.message.channel.history(limit=limit,
                                                                              before=self.message,
                                                                              after=self.start_time,
                                                                              oldest_first=False)]
        messages.reverse()
        for i, message in reversed(list(enumerate(messages))):
            if i != 0:
                time_diff = (message.created_at -
                             messages[i-1].created_at).total_seconds()
            else:
                time_diff = (messages[0].created_at -
                             self.message.created_at).total_seconds()

            if abs(time_diff) > await self.config.guild(self.message.guild).messages_backread_seconds():
                if i == 0:
                    messages = []
                else:
                    messages = messages[i:]
                break

        history = []
        for i, message in enumerate(messages):
            if self.is_not_valid_message(message):
                history.append(
                    {"role": "system", "content": "A message was skipped"})
                continue
            if message.reference:
                await self._handle_reply_in_history(history, message)
            history.append(self._format_message(message))

        return history

    async def _handle_reply_in_history(self, history: list, message: Message):
        try:
            replied_message = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
        except:
            return
        if self.is_not_valid_message(replied_message):
            return
        if len(history) > 0 and history[-1].get("id", -1) == replied_message.id:
            return
        formatted_replied_message = self._format_message(replied_message)
        if not self.is_id_in_messages(replied_message.id, history):
            history.append(formatted_replied_message)
        else:
            # avoid duplicates that will confuse the model
            history.append(
                {"role": "system", "content": f'The following message is a reply to: User "{replied_message.author.name}" said: {replied_message.content}'})

    def _format_message(self, message: Message) -> Dict[str, str]:
        """ Formats a message into a JSON format for OpenAI """
        role = "user" if message.author != self.bot else "assistant"
        message_content = self._mention_to_text(message)
        content = f'User "{message.author.name}" said: {message_content}' if role == "user" else message_content
        return {"id": message.id, "role": role, "content": content}

    @staticmethod
    def is_not_valid_message(message: Message) -> bool:
        return (not message.content) or len(message.attachments) >= 1 or len(message.content.split(" ")) > MAX_MESSAGE_LENGTH

    @staticmethod
    def is_id_in_messages(id, messages):
        for message in messages:
            if message["role"] == "system":
                continue
            if id == message["id"]:
                return True
        return False

    @staticmethod
    def remove_id_field_in_prompt(prompt):
        for message in prompt:
            if "id" not in message:
                continue
            del message["id"]

    @staticmethod
    def _mention_to_text(message: Message) -> str:
        """
        Converts mentions to text
        """
        content = message.content
        mentions = message.mentions + message.role_mentions + message.channel_mentions

        if not mentions:
            return content

        for mentioned in mentions:
            mention = mentioned.mention.replace("!", "")
            if mentioned in message.channel_mentions:
                content = content.replace(mention, f'#{mentioned.name}')
            else:
                content = content.replace(mention, f'@{mentioned.name}')

        return content
