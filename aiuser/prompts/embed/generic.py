import logging
from typing import Optional

from aiuser.prompts.base import Prompt
from aiuser.prompts.common.helpers import format_embed_content, is_embed_valid
from aiuser.prompts.common.messagethread import MessageThread

logger = logging.getLogger("red.bz_cogs.ai_user")


class GenericEmbedPrompt(Prompt):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _handle_message(self) -> Optional[MessageThread]:
        if not is_embed_valid(self.message):
            return None

        await self.messages.add_msg(format_embed_content(self.message), self.message)

        return self.messages
