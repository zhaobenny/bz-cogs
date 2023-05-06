
import logging
import random
import discord
import openai
from datetime import datetime, timezone
from redbot.core import Config, app_commands, commands
from redbot.core.bot import Red

from ai_user.abc import CompositeMetaClass
from ai_user.prompts.prompt_factory import create_prompt_instance
from ai_user.prompts.constants import MIN_MESSAGE_LENGTH, MAX_MESSAGE_LENGTH
from ai_user.response.response import generate_response
from ai_user.settings import Settings

logger = logging.getLogger("red.bz_cogs.ai_user")


class AI_User(Settings, commands.Cog, metaclass=CompositeMetaClass):
    """ Utilize OpenAI to reply to messages and images in approved channels. """

    def __init__(self, bot):
        super().__init__()
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=754070)
        self.cached_options = {}
        self.override_prompt_start_time = {}

        default_guild = {
            "reply_percent": 0.5,
            "messages_backread": 10,
            "messages_backread_seconds": 60 * 120,
            "reply_to_mentions_replies": False,
            "scan_images": False,
            "filter_responses": True,
            "model": "gpt-3.5-turbo",
            "custom_text_prompt": None,
            "channels_whitelist": [],
            "public_forget": False,
        }

        default_member = {
            "custom_text_prompt": None,
        }

        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)

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

        start_time = self.override_prompt_start_time.get(ctx.guild.id, None)
        prompt_instance = await create_prompt_instance(ctx.message, self.config, start_time)
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
        elif random.random() > self.cached_options[message.guild.id].get("reply_percent"):
            return

        start_time = self.override_prompt_start_time.get(ctx.guild.id, None)
        prompt_instance = await create_prompt_instance(message, self.config, start_time)
        prompt = await prompt_instance.get_prompt()
        if prompt is None:
            return

        return await generate_response(ctx, self.config, prompt)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """ Catch embed updates """

        ctx: commands.Context = await self.bot.get_context(after)
        if not await self.is_common_valid_reply(ctx):
            return

        time_diff = datetime.now(timezone.utc) - after.created_at
        if not (time_diff.total_seconds() <= 10):
            return

        if random.random() > self.cached_options[before.guild.id].get("reply_percent"):
            return

        prompt = None
        if len(before.embeds) != len(after.embeds):
            start_time = self.override_prompt_start_time.get(before.guild.id, None)
            prompt_instance = await create_prompt_instance(after, self.config, start_time)
            prompt = await prompt_instance.get_prompt()
        if prompt is None:
            return

        return await generate_response(ctx, self.config, prompt)

    async def is_common_valid_reply(self, ctx: commands.Context) -> bool:
        """ Run some common checks to see if a message is valid for the bot to reply to """
        if not ctx.guild or ctx.author.bot:
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

        if not self.cached_options.get(ctx.message.guild.id):
            await self.cache_guild_options(ctx)

        if ctx.interaction:
            return True

        if isinstance(ctx.channel, discord.Thread):
            if ctx.channel.parent.id not in self.cached_options[ctx.guild.id].get("channels_whitelist"):
                return False
        elif ctx.channel.id not in self.cached_options[ctx.guild.id].get("channels_whitelist"):
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
