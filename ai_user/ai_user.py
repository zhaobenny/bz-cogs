import datetime
import importlib
import json
import logging
import random
import re

import discord
import openai
from redbot.core import Config, checks, commands

from ai_user.prompts.embed_prompt import EmbedPrompt
from ai_user.prompts.text_prompt import TextPrompt

logger = logging.getLogger("red.bz_cogs.ai_user")
logger.setLevel(logging.INFO)


try:
    importlib.import_module("pytesseract")
    importlib.import_module("torch")
    importlib.import_module("transformers")
    from ai_user.prompts.image_prompt import ImagePrompt
except:
    from ai_user.prompts.dummy_image_prompt import ImagePrompt
    logger.warning("No image processing dependencies installed / supported.")


class AI_User(commands.Cog):
    whitelist = None

    def __init__(self, bot):

        self.bot = bot
        self.config = Config.get_conf(self, identifier=754070)
        self.whitelist = {}
        self.percent = {}

        default_global = {
            "scan_images": False,
            "model": "gpt-3.5-turbo",
            "filter_responses": True,
        }

        default_guild = {
            "channels_whitelist": [],
            "custom_text_prompt": None,
            "custom_image_prompt": None,
            "reply_percent": 0.5,
        }

        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def initalize_openai(self, message):
        openai.api_key = (await self.bot.get_shared_api_tokens("openai")).get("api_key")
        if not openai.api_key:
            return await message.channel.send("OpenAI API key not set. Please set it with `[p]set api openai api_key,API_KEY`")

    @commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name, api_tokens):
        if service_name == "openai":
            openai.api_key = api_tokens.get("api_key")

    @commands.group()
    async def ai_user(self, _):
        pass

    @ai_user.command()
    async def logging(self, ctx):
        """Toggle debug logging for troubleshooting"""
        value = not logger.isEnabledFor(logging.INFO)
        logger.setLevel(logging.INFO if value else logging.DEBUG)
        await ctx.send(f"Debug logging {'enabled' if value else 'disabled'}")

    @ai_user.command()
    async def config(self, message):
        """Returns current config"""
        whitelist = await self.config.guild(message.guild).channels_whitelist()
        channels = [f"<#{channel_id}>" for channel_id in whitelist]

        embed = discord.Embed(title="AI User Settings")
        embed.add_field(name="Scan Images", value=await self.config.scan_images(), inline=False)
        embed.add_field(name="Model", value=await self.config.model(), inline=False)
        embed.add_field(name="Filter Responses", value=await self.config.filter_responses(), inline=False)
        embed.add_field(name="Server Reply Percent", value=f"{await self.config.guild(message.guild).reply_percent() * 100}%", inline=False)
        embed.add_field(name="Server Whitelisted Channels", value=" ".join(
            channels) if channels else "None", inline=False)
        return await message.send(embed=embed)

    @ai_user.command()
    @checks.is_owner()
    async def scan_images(self, ctx):
        """ Toggle image scanning (req. cpu usage / tesseract)"""
        try:
            importlib.import_module("pytesseract")
            importlib.import_module("torch")
            importlib.import_module("transformers")
            value = not await self.config.scan_images()
            await self.config.scan_images.set(value)
            embed = discord.Embed(
                title="⚠️ WILL CAUSE HEAVY CPU LOAD ⚠️")
            embed.add_field(name="Scanning Images now set to", value=value)
            return await ctx.send(embed=embed)
        except:
            await self.config.scan_images.set(False)
            await ctx.send("Image processing dependencies not available. Please install them (see cog README.md) to use this feature.")

    @ai_user.command()
    @checks.is_owner()
    async def percent(self, ctx, new_value):
        """Change the bot's response chance for this server"""
        try:
            new_value = float(new_value)
        except ValueError:
            return await ctx.send("Value must be a number")
        await self.config.guild(ctx.guild).reply_percent.set(new_value / 100)
        self.percent[ctx.guild.id] = new_value / 100
        embed = discord.Embed(
            title="The chance that the bot will reply on this server is now set to")
        embed.add_field(name="", value=f"{new_value}%")
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.is_owner()
    async def model(self, ctx, new_value):
        """ Change default chat completion model """
        if not openai.api_key:
            await self.initalize_openai(ctx)

        models_list = openai.Model.list()
        gpt_models = [model.id for model in models_list['data']
                      if model.id.startswith('gpt')]

        if new_value not in gpt_models:
            return await ctx.send(f"Invalid model. Choose from: {', '.join(gpt_models)}")

        await self.config.model.set(new_value)
        embed = discord.Embed(
            title="The default model is now set to")
        embed.add_field(name="", value=new_value)
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.is_owner()
    async def filter_responses(self, ctx):
        """ Toggle rudimentary filtering of canned replies """
        value = not await self.config.filter_responses()
        await self.config.filter_responses.set(value)
        embed = discord.Embed(
            title="Filtering canned responses now set to")
        embed.add_field(name="", value=value)
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def add(self, ctx, channel_name):
        """Add a channel to the whitelist to allow the bot to reply in"""
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        if channel is None:
            return await ctx.send("Invalid channel name")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id in new_whitelist:
            return await ctx.send("Channel already in whitelist")
        new_whitelist.append(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        self.whitelist[ctx.guild.id] = new_whitelist
        embed = discord.Embed(title="The server whitelist is now")
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.add_field(name="", value=" ".join(
            channels) if channels else "None")
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def remove(self, ctx, channel_name):
        """Remove a channel from the whitelist"""
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        if channel is None:
            return await ctx.send("Invalid channel name")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id not in new_whitelist:
            return await ctx.send("Channel not in whitelist")
        new_whitelist.remove(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        self.whitelist[ctx.guild.id] = new_whitelist
        embed = discord.Embed(title="The server whitelist is now")
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.add_field(name="", value=" ".join(
            channels) if channels else "None")
        return await ctx.send(embed=embed)

    @ai_user.group()
    @checks.is_owner()
    async def prompt(self, _):
        """Change the prompt for the current server"""
        pass

    @prompt.command()
    @checks.is_owner()
    async def reset(self, ctx):
        """Reset prompts to default (cynical)"""
        await self.config.guild(ctx.guild).custom_text_prompt.set(None)
        await self.config.guild(ctx.guild).custom_image_prompt.set(None)
        embed = discord.Embed(title="Prompt resetted")
        return await ctx.send(embed=embed)

    @prompt.command()
    @checks.is_owner()
    async def text(self, ctx, prompt):
        """Set custom text prompt (Enclose with "")"""
        await self.config.guild(ctx.guild).custom_text_prompt.set(prompt)
        embed = discord.Embed(title="Text prompt set to",
                              description=f"{prompt}")
        return await ctx.send(embed=embed)

    @prompt.command()
    @checks.is_owner()
    async def image(self, ctx, prompt):
        """Set custom image prompt (Enclose with "")"""
        await self.config.guild(ctx.guild).custom_image_prompt.set(prompt)
        embed = discord.Embed(title="Image prompt set to",
                              description=f"{prompt}")
        return await ctx.send(embed=embed)

    @prompt.command()
    @checks.admin()
    async def show(self, ctx):
        """Show current custom text and image prompts"""
        custom_text_prompt = await self.config.guild(ctx.guild).custom_text_prompt()
        custom_image_prompt = await self.config.guild(ctx.guild).custom_image_prompt()
        embed = discord.Embed(title="Current Server Prompts")
        if custom_text_prompt:
            embed.add_field(name="Custom Text Prompt",
                            value=custom_text_prompt, inline=False)
        else:
            embed.add_field(name="Custom Text Prompt",
                            value="Not set", inline=False)
        if custom_image_prompt:
            embed.add_field(name="Custom Image Prompt",
                            value=custom_image_prompt, inline=False)
        else:
            embed.add_field(name="Custom Image Prompt",
                            value="Not set", inline=False)
        return await ctx.send(embed=embed)

    async def is_common_valid_reply(self, message) -> bool:
        """Run some common checks to see if a message is valid for the bot to reply to"""
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return False

        if message.author.bot:
            return False

        if self.whitelist.get(message.guild.id, None) is None or self.percent.get(message.guild.id, None) is None:
            # Cache the guild options
            self.whitelist[message.guild.id] = await self.config.guild(message.guild).channels_whitelist()
            self.percent[message.guild.id] = await self.config.guild(message.guild).reply_percent()

        if (message.channel.id not in self.whitelist[message.guild.id]):
            return False

        return True

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if not await self.is_common_valid_reply(message):
            return

        if random.random() > self.percent[message.guild.id]:
            return

        url_pattern = re.compile(r"(https?://\S+)")
        contains_url = url_pattern.search(message.content)
        prompt = None

        if (message.attachments and await self.config.scan_images()):
            default_bot_prompt = await self.config.guild(message.guild).custom_image_prompt()
            image = ImagePrompt(self.bot.user, message,
                                bot_prompt=default_bot_prompt)
            prompt = await image.get_prompt()
        elif not contains_url:
            default_bot_prompt = await self.config.guild(message.guild).custom_text_prompt()
            text = TextPrompt(self.bot.user, message,
                              bot_prompt=default_bot_prompt)
            prompt = await text.get_prompt()
        elif contains_url:
            default_bot_prompt = await self.config.guild(message.guild).custom_text_prompt()
            text = EmbedPrompt(self.bot.user, message,
                               bot_prompt=default_bot_prompt)
            prompt = await text.get_prompt()

        if prompt is None:
            return

        return await self.sent_reply(message, prompt)

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """ Catch embed updates """
        if not await self.is_common_valid_reply(before):
            return

        time_diff = datetime.datetime.utcnow() - after.created_at
        if not (time_diff.total_seconds() <= 20):
            return

        if random.random() > self.percent[after.guild.id]:
            return

        prompt = None
        if len(before.embeds) != len(after.embeds):
            default_bot_prompt = await self.config.guild(after.guild).custom_text_prompt()
            text = EmbedPrompt(self.bot.user, after,
                               bot_prompt=default_bot_prompt)
            prompt = await text.get_prompt()

        if prompt is None:
            return

        return await self.sent_reply(after, prompt, direct_reply=True)

    async def sent_reply(self, message, prompt: list[dict], direct_reply=False):
        """ Generates the reply using OpenAI and sends the result """
        logger.debug(
            f"Replying to message \"{message.content}\" in {message.guild.name} with prompt: \n{json.dumps(prompt, indent=4)}")

        def check_moderated_response(response):
            """ filters out responses that were moderated out """
            response = response.lower()
            filters = ["language model", "openai", "sorry", "apologize"]

            for filter in filters:
                if filter in response:
                    logger.debug(
                        f"Filtered out canned response replying to \"{message.content}\" in {message.guild.name}: \n{response}")
                    return True

            return False

        if not openai.api_key:
            await self.initalize_openai(message)

        model = await self.config.model()
        async with message.channel.typing():
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=prompt,
            )

            try:
                reply = response["choices"][0]["message"]["content"]
            except:
                return logger.error(f"Bad response from OpenAI:\n {response}")

        if (await self.config.filter_responses()) and check_moderated_response(reply):
            return await message.add_reaction("😶")

        pattern = r'^\[.*?\]:\s?'
        # remove the [user]: from the response if it exists
        reply = re.sub(pattern, '', reply)

        time_diff = datetime.datetime.utcnow() - message.created_at
        if time_diff.total_seconds() > 8:
            direct_reply = True

        if not direct_reply:  # randomize if bot will reply directly or not
            direct_reply = (random.random() < 0.25)

        if direct_reply:
            await message.reply(reply, mention_author=False)
        else:
            await message.channel.send(reply)
