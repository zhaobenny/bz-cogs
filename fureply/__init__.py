from .fureply import FuReply

def setup(bot):
    bot.add_cog(FuReply(bot))