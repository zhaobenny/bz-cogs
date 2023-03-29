import logging
logger = logging.getLogger("red.bz_cogs.ai_user")
logger.debug("Attempting to load ai_user cog...")
from .ai_user import AI_User
logger.debug("Loaded ai_user cog...")

async def setup(bot):
    logger.debug("Adding ai_user cog...")
    bot.add_cog(AI_User(bot))
    logger.debug("Added ai_user cog...")
