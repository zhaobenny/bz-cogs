from .core.aiuser import AIUser
from .core.slash import app_install
from redbot.core.utils import get_end_user_data_statement

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot):
    cog = AIUser(bot)
    await app_install(bot, cog)
    await bot.add_cog(cog)
