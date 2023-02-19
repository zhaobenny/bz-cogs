import discord
from redbot.core import commands


class OneLetterOnly(commands.Cog):
    """Changes new user's nickname to first letter of nickname"""

    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        words = member.name.split()
        if (member.bot):
            new_nick = "!" + words[0][0].upper()
        elif (len(words) >= 2):
            new_nick = (words[0][0] + words[1][0]).upper()
        else:
            new_nick = words[0][0].upper()

        await member.edit(nick=new_nick)

        return
