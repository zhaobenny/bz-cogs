import logging
import random

import discord
import tiktoken
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

from .openai_utils import setup_openai_client
from .settings import DEFAULT_LLM_MODEL, Settings

logger = logging.getLogger("red.bz_cogs.aiemote")

_ = Translator("AIEmote", __file__)


@cog_i18n(_)
class AIEmote(commands.Cog, Settings):
    """Human-like Discord reacts to messages powered by OpenAI."""

    __version__ = "2.0"
    __author__ = "zhaobenny"
    __contributor__ = "evanroby"

    def __init__(self, bot):
        super().__init__()
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=754069)
        self.aclient = None
        self.llm_model = DEFAULT_LLM_MODEL
        self.encoding = None

        default_global = {
            "percent": 50,
            "global_emojis": [
                {
                    "description": _("A happy face"),
                    "emoji": "😀",
                },
                {
                    "description": _("A sad face"),
                    "emoji": "😢",
                },
            ],
            "extra_instruction": "",
            "optin": [],
            "optout": [],
            "llm_model": DEFAULT_LLM_MODEL,
            "custom_openai_endpoint": None,
        }

        default_guild = {"server_emojis": [], "whitelist": [], "optin_by_default": False}

        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

    async def cog_load(self):
        self.whitelist = {}
        all_config = await self.config.all_guilds()
        self.percent = await self.config.percent()
        self.optin_users = await self.config.optin()
        self.optout_users = await self.config.optout()
        self.llm_model = await self.config.llm_model()
        try:
            self.encoding = tiktoken.encoding_for_model(self.llm_model)
        except KeyError:
            self.encoding = None

        for guild_id, config in all_config.items():
            self.whitelist[guild_id] = config["whitelist"]

        self.aclient = await setup_openai_client(self.bot, self.config)

    def format_help_for_context(self, ctx):
        pre_processed = super().format_help_for_context(ctx)
        n = "\n" if "\n\n" not in pre_processed else ""
        return (
            f"{pre_processed}{n}\n"
            f"{_('Cog Version')}: {self.__version__}\n"
            f"{_('Cog Author')}: {self.__author__}\n"
            f"{_('Cog Contributor')}: {self.__contributor__}"
        )

    @commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name, api_tokens):
        if service_name in ["openai", "openrouter"]:
            self.aclient = await setup_openai_client(self.bot, self.config)

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        ctx: commands.Context = await self.bot.get_context(message)
        if not (await self.is_valid_to_react(ctx)):
            return
        if self.percent < random.randint(0, 99):
            return
        emoji = await self.pick_emoji(message)
        if emoji:
            await message.add_reaction(emoji)

    async def pick_emoji(self, message: discord.Message):
        options = "\n"
        emojis = await self.config.guild(message.guild).server_emojis() or []
        emojis += await self.config.global_emojis() or []

        if not emojis:
            logger.warning(
                _("Skipping react! No valid emojis to use in {guild_name}").format(
                    guild_name=message.guild.name
                )
            )
            return None

        for index, value in enumerate(emojis):
            options += f"{index}. {value['description']}\n"

        logit_bias = {}
        try:
            if not self.encoding:
                raise KeyError
            for i in range(len(emojis)):
                encoded_value = self.encoding.encode(str(i))
                if len(encoded_value) == 1:
                    logit_bias[encoded_value[0]] = 100
        except (KeyError, AttributeError):
            logit_bias = {}

        system_prompt = _(
            "You are in a chat room. You will pick an emoji for the following message. {extra_instruction} "
            "Here are your options: {options} Your answer will be a int between 0 and {max_index}."
        ).format(
            extra_instruction=await self.config.extra_instruction(),
            options=options,
            max_index=len(emojis) - 1,
        )

        content = f"{message.author.display_name} : {self.stringify_any_mentions(message)}"
        try:
            response = await self.aclient.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                max_tokens=1,
                logit_bias=logit_bias,
            )
        except Exception:
            logger.exception(
                _("Skipping react in {guild_name}! Failed to get response from OpenAI").format(
                    guild_name=message.guild.name
                )
            )
            return None

        response = response.choices[0].message.content
        if response.isnumeric():
            index = int(response)
            if index < 0 or index >= len(emojis):
                return None
            partial_emoji = discord.PartialEmoji.from_str(emojis[index]["emoji"])
            return partial_emoji
        else:
            logger.warning(
                _(
                    "Skipping react in {guild_name}! Non-numeric response from OpenAI: {response}. "
                    "(Please report to dev if this occurs often)"
                ).format(guild_name=message.guild.name, response=response)
            )
            return None

    async def is_valid_to_react(self, ctx: commands.Context):
        if ctx.guild is None or ctx.author.bot:
            return False

        whitelist = self.whitelist.get(ctx.guild.id, [])
        if await self.bot.cog_disabled_in_guild(self, ctx.guild):
            return False

        if not isinstance(ctx.channel, discord.Thread) and (ctx.channel.id not in whitelist):
            return False
        if isinstance(ctx.channel, discord.Thread) and (ctx.channel.parent_id not in whitelist):
            return False

        if not await self.bot.ignored_channel_or_guild(ctx):
            return False
        if not await self.bot.allowed_by_whitelist_blacklist(ctx.author):
            return False
        if ctx.author.id in self.optout_users:
            return False
        if (ctx.author.id not in self.optin_users) and (
            not (await self.config.guild(ctx.guild).optin_by_default())
        ):
            return False

        if not self.aclient:
            self.aclient = await setup_openai_client(self.bot, self.config, ctx)
            if not self.aclient:
                return False

        # skipping images / embeds
        if not ctx.message.content or (
            ctx.message.attachments and len(ctx.message.attachments) > 0
        ):
            return False

        # skipping long / short messages
        if len(ctx.message.content) > 1500 or len(ctx.message.content) < 10:
            logger.debug(
                _("Skipping message in {guild_name} with length {length}").format(
                    guild_name=ctx.guild.name, length=len(ctx.message.content)
                )
            )
            return False

        return True

    def stringify_any_mentions(self, message: discord.Message) -> str:
        """
        Converts mentions to text
        """
        content = message.content
        mentions = message.mentions + message.role_mentions + message.channel_mentions

        if not mentions:
            return content

        for mentioned in mentions:
            if mentioned in message.channel_mentions:
                content = content.replace(mentioned.mention, f"#{mentioned.name}")
            elif mentioned in message.role_mentions:
                content = content.replace(mentioned.mention, f"@{mentioned.name}")
            else:
                content = content.replace(mentioned.mention, f"@{mentioned.display_name}")

        return content
