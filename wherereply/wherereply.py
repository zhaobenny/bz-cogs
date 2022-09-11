import discord
from discord.utils import get
from redbot.core import commands


class WhereReply(commands.Cog):
    """Auto-replies to my friends' classic phrase"""

    def __init__(self, bot):
        self.bot = bot

    async def sent_idk_msg(self, message):
        async with message.channel.typing():
            await message.channel.send(f"idk where is benny, {message.author.display_name}.")
        return

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if message.author.bot:
            return
        message_text = message.content.lower()
        if message_text == "where benny":
            await self.sent_idk_msg(message)
        elif "where" in message_text and len(message.mentions) == 1 and message.mentions[0].id == 269670939480817664:
            await self.sent_idk_msg(message)
