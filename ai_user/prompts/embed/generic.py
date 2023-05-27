import logging
from typing import Optional

from ai_user.prompts.base import Prompt
from ai_user.prompts.common.helpers import format_embed_content
from ai_user.prompts.common.messages_list import MessagesList

logger = logging.getLogger("red.bz_cogs.ai_user")


class GenericEmbedPrompt(Prompt):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _handle_message(self) -> Optional[MessagesList]:
        if len(self.message.embeds) == 0 or not self.message.embeds[0].title or not self.message.embeds[0].description:
            logger.debug(
                f"Skipping unloaded / unsupported embed in {self.message.guild.name}")
            return None

        await self.messages.add_msg(format_embed_content(self.message), self.message)

        return self.messages
