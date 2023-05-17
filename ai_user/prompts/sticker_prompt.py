import logging
from typing import Optional
from discord import Message
from redbot.core import Config

from ai_user.common.types import ContextOptions
from ai_user.prompts.base import Prompt
from ai_user.prompts.common.helpers import format_sticker_content
from ai_user.prompts.common.messages_list import MessagesList

logger = logging.getLogger("red.bz_cogs.ai_user")


class StickerPrompt(Prompt):
    def __init__(self, message: Message, config: Config, context_options: ContextOptions):
        super().__init__(message, config, context_options)

    async def _handle_message(self) -> Optional[MessagesList]:
        if not self.message.stickers:
            return

        await self.messages.add_msg((await format_sticker_content(self.message)), self.message)

        return self.messages
