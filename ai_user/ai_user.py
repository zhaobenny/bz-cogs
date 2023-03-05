import random

import discord
import openai
from redbot.core import Config, checks, commands


class AI_User(commands.Cog):
    whitelist = None

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=754070)
        default_global = {
            "reply_percent": 0.5,
        }

        default_guild = {
            "channels_whitelist": []
        }

        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def initalize_openai(self, message):
        openai.api_key = (await self.bot.get_shared_api_tokens("openai")).get("api_key")
        if not openai.api_key:
            return await message.channel.send("OpenAI API key not set. Please set it with `[p]set api openai api_key,API_KEY`")

    @commands.group()
    async def ai_user(self, ctx):
        """AI User Settings"""
        pass

    @ai_user.command()
    @checks.is_owner()
    async def reply_percent(self, ctx, new_value):
        """Set the percent chance the bot will reply to a any given message (defaults to 50 for 50%) """
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
        whitelist = (await self.config.guild(ctx.guild).channels_whitelist())
        whitelist.remove(int(new_value))
        await self.config.guild(ctx.guild).channels_whitelist.set(whitelist)
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        await ctx.send("Removed, whitelist is now: " + str(whitelist))

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if self.whitelist is None:
            self.whitelist = await self.config.guild(message.guild).channels_whitelist()

        if (message.channel.id not in self.whitelist or self.skip_reply(message) or
                (len(message.content.split(" ")) == 1 and (random.random() > 0.5)) or len(message.content) < 5):
            return

        percent = await self.config.reply_percent()
        if random.random() > percent:
            return

        if not openai.api_key:
            await self.initalize_openai(message)

        async with message.channel.typing():
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=await self.create_messages(message),
            )

            try:
                reply = response["choices"][0]["message"]["content"]
            except:
                print("Bad response from OpenAI:")
                print(response)
                print()
                return

            if self.check_safe_response(reply):
                return

            await message.channel.send(reply)

    def skip_reply(self, message):
        # conditons to skip on

        if len(message.attachments) >= 1 or message.author.bot or len(message.mentions) > 0:  # not worth it
            return True
        words = message.content.split(" ")
        if len(words) > 300:
            return True
        return False

    async def create_messages(self, message: discord.Message):
        """ Create a list of messages to send to OpenAI """

        # get the last 10 messages before the current message
        history = await message.channel.history(limit=10, before=message).flatten()
        history.reverse()

        messages = [
            {"role": "system",
                     "content": "You are in a Discord text channel. Respond to anything, including URLs, unhelpfully and cynically in a short message."},
        ]

        i = 0
        while (i < len(history)):
            # check if time between messages is more than 20 minutes
            if i > 0 and (history[i].created_at - history[i - 1].created_at).total_seconds() > 1188:
                break
            if history[i].author.id == self.bot.user.id:
                messages.append(
                    {"role": "assistant", "content": history[i].content})
                i += 1
                continue
            elif (self.skip_reply(history[i])):
                break
            else:
                messages.append(
                    {"role": "user", "content": history[i].author.name + ":  " + history[i].content})
            i += 1

        messages.append({"role": "user", "content": message.author.name + ":  " + message.content})

        print(messages)
        return messages

    def check_safe_response(self, response):
        """ filters out responses that were moderated out """
        response = response.lower()
        filters = ["language model", "openai", "i'm sorry"]

        for filter in filters:
            if filter in response:
                return True

        return False