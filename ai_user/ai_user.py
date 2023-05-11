
import logging
import random
import re
from datetime import datetime, timezone

import discord
import openai
from redbot.core import Config, app_commands, commands
from redbot.core.bot import Red

from ai_user.abc import CompositeMetaClass
from ai_user.constants import AI_HORDE_MODE, DEFAULT_REPLY_PERCENT, IMAGE_RESOLUTION, MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH
from ai_user.prompts.embed_prompt import EmbedPrompt
from ai_user.prompts.image.ai_horde import AIHordeImagePrompt
from ai_user.prompts.text_prompt import TextPrompt
from ai_user.response.response import generate_response
from ai_user.settings import Settings

logger = logging.getLogger("red.bz_cogs.ai_user")

class AI_User(Settings, commands.Cog, metaclass=CompositeMetaClass):
    """ Utilize OpenAI to reply to messages and images in approved channels. """

    def __init__(self, bot):
        super().__init__()
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=754070)
        # cached options
        self.channels_whitelist: dict[int, list[int]] = {}
        self.reply_percent: dict[int, float] = {}
        self.ignore_regex: dict[int, re.Pattern] = {}
        self.override_prompt_start_time: dict[int, datetime] = {}

        default_guild = {
            "reply_percent": DEFAULT_REPLY_PERCENT,
            "messages_backread": 10,
            "messages_backread_seconds": 60 * 120,
            "reply_to_mentions_replies": False,
            "scan_images": False,
            "scan_images_mode": AI_HORDE_MODE,
            "max_image_size": 2 * (1024 * 1024),
            "filter_responses": True,
            "model": "gpt-3.5-turbo",
            "custom_text_prompt": None,
            "channels_whitelist": [],
            "public_forget": False,
            "ignore_regex": None,
        }
        default_member = {
            "custom_text_prompt": None,
        }
        default_channel = {
            "custom_text_prompt": None,
        }

        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)
        self.config.register_channel(**default_channel)

    async def cog_load(self):
        all_config = await self.config.all_guilds()
        for guild_id, config in all_config.items():
            self.channels_whitelist[guild_id] = config["channels_whitelist"]
            self.reply_percent[guild_id] = config["reply_percent"]
            pattern = config["ignore_regex"]
            self.ignore_regex[guild_id] = re.compile(pattern) if pattern else None

    async def red_delete_data_for_user(self, *, requester, user_id: int):
        for guild in self.bot.guilds:
            member = guild.get_member(user_id)
            if member:
                await self.config.member(member).clear()

    @app_commands.command(name="chat")
    @app_commands.describe(text="The prompt you want to send to the AI.")
    @app_commands.checks.cooldown(1, 30)
    @app_commands.checks.cooldown(1, 5, key=None)
    async def slash_command(self, inter: discord.Interaction, *,
                            text: app_commands.Range[str, MIN_MESSAGE_LENGTH, MAX_MESSAGE_LENGTH]):
        """ Talk directly to this bot's AI. Ask it anything you want! """
        ctx = await commands.Context.from_interaction(inter)
        ctx.message.content = text
        if not await self.is_common_valid_reply(ctx):
            return await ctx.send("You're not allowed to use this command here.", ephemeral=True)

        prompt_instance = await self.create_prompt_instance(ctx)
        prompt = await prompt_instance.get_prompt()
        if prompt is None:
            return await ctx.send("Error: No prompt set.", ephemeral=True)

        await generate_response(ctx, self.config, prompt)

    @commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name, api_tokens):
        if service_name == "openai":
            openai.api_key = api_tokens.get("api_key")

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        ctx: commands.Context = await self.bot.get_context(message)
        if not await self.is_common_valid_reply(ctx):
            return

        if await self.is_bot_mentioned_or_replied(message):
            pass
        elif random.random() > self.reply_percent.get(message.guild.id, DEFAULT_REPLY_PERCENT):
            return

        prompt_instance = await self.create_prompt_instance(ctx)
        prompt = await prompt_instance.get_prompt()
        if prompt is None:
            return

        return await generate_response(ctx, self.config, prompt)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """ Catch embeds loading """
        ctx: commands.Context = await self.bot.get_context(after)
        if not await self.is_common_valid_reply(ctx):
            return

        time_diff = datetime.now(timezone.utc) - after.created_at
        if not (time_diff.total_seconds() <= 10):
            return

        if random.random() > self.reply_percent.get(before.guild.id, DEFAULT_REPLY_PERCENT):
            return

        prompt = None
        if len(before.embeds) != len(after.embeds):
            prompt_instance = await self.create_prompt_instance(ctx)
            prompt = await prompt_instance.get_prompt()
        if prompt is None:
            return

        return await generate_response(ctx, self.config, prompt)

    async def is_common_valid_reply(self, ctx: commands.Context) -> bool:
        """ Run some common checks to see if a message is valid for the bot to reply to """
        if not ctx.guild or ctx.author.bot or not self.channels_whitelist.get(ctx.guild.id, []):
            return False
        if not ctx.interaction and (
            isinstance(ctx.channel, discord.Thread) and ctx.channel.parent.id not in self.channels_whitelist[ctx.guild.id]
            or ctx.channel.id not in self.channels_whitelist[ctx.guild.id]
        ):
            return False
        if self.ignore_regex[ctx.guild.id] and self.ignore_regex[ctx.guild.id].search(ctx.message.content):
            return False
        if await self.bot.cog_disabled_in_guild(self, ctx.guild):
            return False
        if not await self.bot.ignored_channel_or_guild(ctx):
            return False
        if not await self.bot.allowed_by_whitelist_blacklist(ctx.author):
            return False

        if not openai.api_key:
            await self.initalize_openai(ctx)
        if not openai.api_key:
            return False

        return True

    async def is_bot_mentioned_or_replied(self, message) -> bool:
        if not (await self.config.guild(message.guild).reply_to_mentions_replies()):
            return False
        if self.bot.user in message.mentions:
            return True
        if message.reference and message.reference.message_id:
            reference_message = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
            return reference_message.author == self.bot.user
        return False

    async def initalize_openai(self, ctx: commands.Context):
        openai.api_key = (await self.bot.get_shared_api_tokens("openai")).get("api_key")
        if not openai.api_key:
            await ctx.send(
                f"OpenAI API key not set for `ai_user`. "
                f"Please set it with `{ctx.clean_prefix}set api openai api_key,API_KEY`")

    async def create_prompt_instance(self, ctx: commands.Context):
        message = ctx.message
        start_time = self.override_prompt_start_time.get(message.guild.id, None)
        url_pattern = re.compile(r"(https?://\S+)")
        contains_url = url_pattern.search(message.content)
        if message.attachments and await self.config.guild(message.guild).scan_images():
            async with ctx.typing():
                if await self.config.guild(message.guild).scan_images_mode() == "local":
                    try:
                        from ai_user.prompts.image.local import \
                            LocalImagePrompt
                        return LocalImagePrompt(message, self.config, start_time)
                    except ImportError:
                        logger.error(
                            f"Unable to load image scanning dependencies, disabling image scanning for this server f{message.guild.name}...")
                        await self.config.guild(message.guild).scan_images.set(False)
                        raise
                elif await self.config.guild(message.guild).scan_images_mode() == "ai-horde":
                    return AIHordeImagePrompt(message, self.config, start_time, self.bot)
        elif contains_url:
            return EmbedPrompt(message, self.config, start_time)
        else:
            return TextPrompt(message, self.config, start_time)
