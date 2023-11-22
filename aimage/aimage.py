import base64
import io
import logging

import aiohttp
import discord
from redbot.core import Config, app_commands, checks, commands
from redbot.core.bot import Red

from aimage.abc import CompositeMetaClass
from aimage.constants import (DEFAULT_BADWORDS_BLACKLIST,
                              DEFAULT_NEGATIVE_PROMPT)
from aimage.settings import Settings
from aimage.views import ImageActions

logger = logging.getLogger("red.bz_cogs.aiimage")


class AImage(Settings,
             commands.Cog,
             metaclass=CompositeMetaClass):
    """ Generate images using a Stable Diffusion endpoint """

    def __init__(self, bot):
        super().__init__()
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=75567113)

        default_global = {
            "endpoint": None,
            "words_blacklist": DEFAULT_BADWORDS_BLACKLIST
        }

        default_guild = {
            "endpoint": None,
            "words_blacklist": DEFAULT_BADWORDS_BLACKLIST,
            "negativeprompt": DEFAULT_NEGATIVE_PROMPT,
            "cfg": 7,
            "sampling_steps": 20,
            "sampler": "Euler a",
        }

        self.session = aiohttp.ClientSession()
        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

    async def red_delete_data_for_user(self, **kwargs):
        return

    async def cog_unload(self):
        await self.session.close()

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @checks.bot_has_permissions(attach_files=True)
    @checks.bot_in_a_guild()
    async def paint(self, ctx: commands.Context, *, prompt: str):
        """
        Generate an image using Stable Diffusion

        **Arguments**
            - `prompt` a prompt to generate an image from
        """
        endpoint = await self._get_endpoint(ctx)

        if not endpoint:
            return await ctx.send(":warning: Endpoint not yet set for this server!")

        blacklist = await self._get_blacklist(ctx)
        if any(word in prompt.lower() for word in blacklist):
            return await ctx.send(":warning: Prompt contains blacklisted words!")

        await ctx.react_quietly("⏳")

        payload = {
            "prompt": prompt,
            "cfg": await self.config.guild(ctx.guild).cfg(),
            "negativeprompt": await self.config.guild(ctx.guild).negativeprompt(),
            "steps": await self.config.guild(ctx.guild).sampling_steps()
        }

        try:
            async with ctx.typing():
                image_data = await self._post_sd_endpoint(endpoint, payload)
        except:
            logger.exception("Failed request to Stable Diffusion endpoint")
            return await ctx.react_quietly(":warning:")
        finally:
            await ctx.message.remove_reaction("⏳", ctx.me)

        await ctx.react_quietly("✅")

        await ctx.send(file=discord.File(io.BytesIO(image_data), filename=f"{ctx.message.id}.png"), view=ImageActions(payload=payload, bot=self.bot, author=ctx.author))

    @app_commands.command(name="paint")
    @app_commands.describe(
        prompt="The prompt to generate an image from",
        negative_prompt="The negative prompt to use",
        steps="The sampling steps to use",
        cfg="The cfg to use",
        seed="The seed to use"
    )
    @app_commands.checks.cooldown(1, 5, key=None)
    @app_commands.checks.bot_has_permissions(attach_files=True)
    @app_commands.guild_only()
    async def paint_app(self, interaction: discord.Interaction, prompt: str, negative_prompt: str = None, cfg: app_commands.Range[float, 1, 30] = None, steps: app_commands.Range[int, 1, 150] = None, seed: app_commands.Range[int, -1, None] = -1):
        """
        Generate an image using Stable Diffusion
        """
        ctx = await self.bot.get_context(interaction)

        endpoint = await self._get_endpoint(ctx)
        if not endpoint:
            return await interaction.response.send_message(content=":warning: Endpoint not yet set for this server!", ephemeral=True)

        blacklist = await self._get_blacklist(ctx)
        if any(word in prompt.lower() for word in blacklist):
            return interaction.response.send_message(":warning: Prompt contains blacklisted words!")

        await interaction.response.defer()

        payload = {
            "prompt": prompt,
            "cfg": cfg or await self.config.guild(ctx.guild).cfg(),
            "negativeprompt": negative_prompt or await self.config.guild(ctx.guild).negativeprompt(),
            "steps": steps or await self.config.guild(ctx.guild).sampling_steps(),
            "seed": seed
        }

        try:
            image_data = await self._post_sd_endpoint(endpoint, payload)
        except:
            logger.exception("Failed request to Stable Diffusion endpoint")
            return await interaction.followup.send(content=":warning: Something went wrong!", ephemeral=True)

        await interaction.followup.send(file=discord.File(io.BytesIO(image_data), filename=f"image.png"), view=ImageActions(payload=payload, bot=self.bot, author=ctx.author))


    async def _get_endpoint(self, ctx):
        endpoint = await self.config.guild(ctx.guild).endpoint()
        if not endpoint:
            endpoint = await self.config.endpoint()
        return endpoint

    async def _get_blacklist(self, ctx):
        endpoint = await self.config.guild(ctx.guild).endpoint()
        if endpoint:
            blacklist = await self.config.guild(ctx.guild).words_blacklist()
        else:
            blacklist = await self.config.words_blacklist()

        return blacklist

    async def _post_sd_endpoint(self, endpoint, payload):
        async with self.session.post(url=endpoint, json=payload) as response:
            if response.status != 200:
                response.raise_for_status()
            r = await response.json()
            image_data = base64.b64decode(r["images"][0])
        return image_data
