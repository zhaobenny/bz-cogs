from .sarcasticreply import SarcasticReply


def setup(bot):
    bot.add_cog(SarcasticReply(bot))