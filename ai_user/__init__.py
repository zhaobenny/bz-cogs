from .ai_user import AI_User

async def setup(bot):
    await bot.add_cog(AI_User(bot))
