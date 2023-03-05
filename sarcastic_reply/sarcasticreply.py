import random
import discord
from redbot.core import commands
import openai


class SarcasticReply(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if len(message.attachments) >= 1 or message.author.bot or len(message.content) < 5 or len(message.content) > 888 or message.channel.nsfw:
            return
        if random.random() < 0.9:
            return

        openai.api_key = (await self.bot.get_shared_api_tokens("openai")).get("api_key")


        if not openai.api_key:
            return await message.channel.send("OpenAI API key not set. Please set it with `[p]set api openai api_key,API_KEY`")

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                    "content": "You are in a Discord text channel. Respond unhelpfully and cynically in a short message"},
                {"role": "user", "content": message.content},
            ]
        )

        if response["choices"]:
            await message.channel.send(response["choices"][0]["message"]["content"])

