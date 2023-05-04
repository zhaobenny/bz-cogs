from typing import Dict, Optional

from discord import Message

from ai_user.prompts.constants import DEFAULT_PROMPT


class Prompt:
    def __init__(self, message: Message, config):
        self.config = config
        self.bot = message.guild.me
        self.message = message

    async def _create_prompt(self, bot_prompt: str) -> Optional[str]:
        raise NotImplementedError(
            "_create_full_prompt() must be implemented in subclasses")

    async def get_prompt(self) -> Optional[str]:
        """
            Returns a list of messages to be used as the prompt for the OpenAI API
        """

        bot_prompt = await self.config.member(self.message.author).custom_text_prompt()
        if bot_prompt is None:
            bot_prompt = await self.config.guild(self.message.guild).custom_text_prompt() or DEFAULT_PROMPT
        full_prompt = await self._create_prompt(bot_prompt)
        if full_prompt is None:
            return None
        self.remove_id_field_in_prompt(full_prompt)
        return full_prompt

    async def _get_previous_history(self, limit: int = 10):
        """ Returns a history of messages before current message """
        messages =  [message async for message in self.message.channel.history(limit=10, before=self.message)]

        messages.reverse()
        for i, message in reversed(list(enumerate(messages))):
            time_diff = 0
            if i != 0:
                time_diff = (message.created_at -
                             messages[i-1].created_at).total_seconds()
            else:
                time_diff = (messages[0].created_at -
                             self.message.created_at).total_seconds()

            if abs(time_diff) > 7200:
                if i == 0:
                    messages = []
                else:
                    messages = messages[i:]
                break

        history = []
        for i, message in enumerate(messages):
            if self.is_not_valid_message(message):
                history.append(
                    {"role": "system", "content": "A message containing an attachment/image or was too long was skipped from this history"})
                continue
            if message.reference:
                await self._handle_historical_reply(history, message)
            history.append(self._format_message(message))

        return history

    async def _handle_historical_reply(self, history, message):
        try:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
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
        message_content = Prompt._mention_to_text(message)
        content = f'User "{message.author.name}" said: {message_content}' if role == "user" else message_content
        return {"id": message.id, "role": role, "content": content}

    @staticmethod
    def is_not_valid_message(message: Message) -> bool:
        return len(message.attachments) >= 1 or len(message.content.split(" ")) > 300

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
