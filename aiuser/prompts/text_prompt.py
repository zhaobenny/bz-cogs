import logging
from typing import Optional

from aiuser.prompts.base import Prompt
from aiuser.prompts.common.helpers import format_text_content
from aiuser.prompts.common.messagethread import MessageThread

logger = logging.getLogger("red.bz_cogs.aiuser")


class TextPrompt(Prompt):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _handle_message(self) -> Optional[MessageThread]:
        await self.messages.add_msg(format_text_content(self.message), self.message)
        return self.messages

