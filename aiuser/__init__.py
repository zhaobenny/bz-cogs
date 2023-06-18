from .aiuser import AIUser
from redbot.core.utils import get_end_user_data_statement

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)

async def setup(bot):
    await bot.add_cog(AIUser(bot))
