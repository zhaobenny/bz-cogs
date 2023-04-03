import logging

from discord import Message, User

from ai_user.prompts.base import Prompt

logger = logging.getLogger("red.bz_cogs.ai_user")


class ImagePrompt(Prompt):
    """ Dummy prompt for when no image dependencies are installed """

    def init(self, bot: User, message: Message, config, bot_prompt: str = None):
        super().init(bot, message, config, bot_prompt)

    async def _create_prompt(self, bot_prompt):
        logger.error(
            "Attempted to reply to a image, but not all required image processing dependencies are installed. (See cog README.md for more info)")
        return None
