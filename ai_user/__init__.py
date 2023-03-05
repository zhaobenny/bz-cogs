from .ai_user import AI_User

def setup(bot):
    bot.add_cog(AI_User(bot))