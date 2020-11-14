import discord
from redbot.core import commands

class OneLetterOnly(commands.Cog):
    """Changes new user's nickname to first letter of nickname"""
    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if (member.bot):
            return
        # if username => 2 words might as well use it as initals
        words = member.name.split(1)
        if (len(words) >= 2):
            new_nick= words[0][1] + words[1][1]
        else:
            new_nick = words[0][1]
        await member.edit(nick=new_nick)
        return