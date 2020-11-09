import discord
from redbot.core import commands

class AutoF(commands.Cog):
    """Big F"""
    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if message.author.bot:
            return
        if message.content == "F":
            await message.channel.send(':regional_indicator_f: :regional_indicator_f: :regional_indicator_f: \n:regional_indicator_f: \n:regional_indicator_f: :regional_indicator_f:\n:regional_indicator_f:\n:regional_indicator_f:')
            return
