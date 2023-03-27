from .ai_user import AI_User

async def setup(bot):
    bot.add_cog(AI_User(bot))