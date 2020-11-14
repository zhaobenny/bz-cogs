from .wherereply import WhereReply

def setup(bot):
    bot.add_cog(WhereReply(bot))