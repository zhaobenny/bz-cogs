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
        await member.edit(nick=member.name[0])
        return