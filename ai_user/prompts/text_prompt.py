import logging
import re
from typing import Optional

from discord import Message, User

from ai_user.prompts.constants import DEFAULT_TEXT_PROMPT
from ai_user.prompts.base import Prompt

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
            logger.debug(f"Skipping short message: {message.content} in {message.guild.name}")
            return False

        if len(message.content.split()) > 300:
            logger.debug(f"Skipping long message: {message.content} in {message.guild.name}")
            return False

        return True

    async def _create_full_prompt(self) -> Optional[str]:
        if not self._is_acceptable_message(self.message):
            return None

        url_pattern = re.compile(r"(https?://\S+)")
        is_url = url_pattern.search(self.message.content)

        tenor_pattern = r"^https:\/\/tenor\.com\/view\/"
        is_tenor_gif = False
        if self.message.embeds:
            is_tenor_gif = re.match(tenor_pattern, self.message.embeds[0].url)

        if is_tenor_gif:  # not handling embeded gifs for now
            return None

        prompt = None

        if len(self.message.embeds) > 0 and self.message.embeds[0].title and self.message.embeds[0].description:
            prompt = [
                {"role": "system",
                 "content": f"You are in a Discord text channel. The following is a embed sent by {self.message.author.name}. {self.bot_prompt}"},
                {"role": "user",
                 "content": f"{self.message.content}, title is \"{self.message.embeds[0].title}\" and the description is \"{self.message.embeds[0].description}\""}
            ]
        elif not is_url:
            prompt = [
                {"role": "system",
                 "content": f"You are {self.bot.name}. Do not include \"[{self.bot.name}]:\" or \"[NAME]\" in the response. Do not react to the username in between the []. You are in a Discord text channel. {self.bot_prompt}"},
            ]
            if self.message.reference:
                replied = await self.message.channel.fetch_message(self.message.reference.message_id)
                if replied.author == self.bot:
                    role = "assistant"
                    content = replied.content
                else:
                    role = "user"
                    content = f"[{replied.author.name}]: {replied.content}"
                prompt.append({"role": role, "content": content})
            prompt.append({"role": "user",
                           "content": f"[{self.message.author.name}]: {self.message.content}"})
            prompt[1:1] = await (self._get_previous_history())
        return prompt
