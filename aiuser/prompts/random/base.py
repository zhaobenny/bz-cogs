import random
from typing import Optional

from aiuser.common.constants import DEFAULT_PROMPT
from aiuser.common.utilities import format_variables
from aiuser.prompts.base import Prompt
from aiuser.prompts.common.messagethread import MessageThread


class RandomEventPrompt(Prompt):
    async def get_list(self) -> Optional[MessageThread]:
        """
            Returns a thread of messages to be used as the prompt for the OpenAI API
        """

        bot_prompt = await self.config.member(self.message.author).custom_text_prompt() \
            or await self.config.channel(self.message.channel).custom_text_prompt() \
            or await self.config.guild(self.message.guild).custom_text_prompt() \
            or DEFAULT_PROMPT

        await self.messages.add_system(format_variables(self.ctx, bot_prompt))

        self.messages = await self._handle_message()

        return self.messages

    async def _handle_message(self) -> Optional[MessageThread]:
        # TODO: pull topics from apis (news? tv show feeds?) for more variety

        topics = await self.config.guild(self.message.guild).random_messages_topics() or ["nothing"]
        topic = format_variables(self.ctx, topics[random.randint(0, len(topics) - 1)])
        await self.messages.add_system(f"You are not responding to a message. Do not greet anyone. You are to start a conversation about the following: {topic}")
        return self.messages
