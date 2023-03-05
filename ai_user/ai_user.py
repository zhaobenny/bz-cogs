import random
import discord
from redbot.core import commands
from redbot.core import Config
from redbot.core import checks
import openai


class AI_User(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=754070)
        default_global = {
            "reply_percent": 0.75,
        }

        default_guild = {
            "channels_whitelist": [""]
        }

        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    @commands.group()
    async def ai_user(self, ctx):
        """AI User Settings"""
        pass

    @ai_user.command()
    @checks.is_owner()
    async def percent(self, ctx, new_value):
        """Set the percent chance the bot will reply to a message (defaults to 75 for 75%) """
        try:
            new_value = float(new_value)
        except ValueError:
            return await ctx.send("Value must be number")
        await self.config.reply_percent.set(new_value / 100)
        return await ctx.send("Set the reply percent to " + str(new_value) + "%")

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def add(self, ctx, new_value):
        """Add a channel to the whitelist to allow the bot to reply in """
        whitelist = (await self.config.guild(ctx.guild).channels_whitelist())
        if not whitelist:
            whitelist = []
        try:
            new_value = int(new_value)
        except ValueError:
            return await ctx.send("Value must be a channel id")
        whitelist.append(new_value)
        await self.config.guild(ctx.guild).channels_whitelist.set(whitelist)
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        await ctx.send("Added, whitelist is now: " + str(whitelist))

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def remove(self, ctx, new_value):
        """Remove a channel from the whitelist that allows the bot to reply in """
        whitelist = (await self.config.guild(ctx.guild).channels_whitelist()).remove(new_value)
        await self.config.guild(ctx.guild).channels_whitelist.set(whitelist)
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        await ctx.send("Removed, whitelist is now: " + str(whitelist))

    async def skip(self, message):
        whitelist = await self.config.guild(message.guild).channels_whitelist()
        if message.channel.id not in whitelist:
            return True
        if len(message.attachments) >= 1 or message.author.bot or message.mentions:
            return True
        if len(message.content) < 5 or len(message.content) > 888:
            return True
        return False

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if await self.skip(message):
            return

        percent = await self.config.reply_percent()
        if random.random() > percent:
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
