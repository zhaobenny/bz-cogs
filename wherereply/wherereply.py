import discord
from redbot.core import commands

class WhereReply(commands.Cog):
    """Auto-replies to my friends' classic phrase"""
    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if message.author.bot:
            return
        if message.content.lower() == "where benny":
            async with message.channel.typing():
                await message.channel.send("idk where is benny, " + format(message.author.display_name) + ".")
            return
