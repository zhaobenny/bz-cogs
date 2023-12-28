import asyncio
import logging
from collections import defaultdict
from typing import List

import aiohttp
import discord
from rapidfuzz import fuzz
from redbot.core import Config, app_commands, checks, commands
from redbot.core.bot import Red

from aimage.abc import CompositeMetaClass
from aimage.constants import (AUTO_COMPLETE_SAMPLERS,
                              DEFAULT_BADWORDS_BLACKLIST,
                              DEFAULT_NEGATIVE_PROMPT)
from aimage.functions import Functions
from aimage.settings import Settings

logger = logging.getLogger("red.bz_cogs.aimage")


class AImage(Settings,
             Functions,
             commands.Cog,
             metaclass=CompositeMetaClass):
    """ Generate images using a A1111 endpoint """

    def __init__(self, bot):
        super().__init__()
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=75567113)

        default_global = {
            "endpoint": None,
            "auth": None,
            "nsfw": True,
            "words_blacklist": DEFAULT_BADWORDS_BLACKLIST,
            "aihorde": True,
        }

        default_guild = {
            "endpoint": None,
            "nsfw": True,
            "words_blacklist": DEFAULT_BADWORDS_BLACKLIST,
            "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
            "cfg": 7,
            "sampling_steps": 20,
            "sampler": "Euler a",
            "checkpoint": None,
            "adetailer": False,
            "width": 512,
            "height": 512,
            "auth": None,
            "aihorde_anime": False,
        }

        self.session = aiohttp.ClientSession()
        self.autocomplete_cache = defaultdict(dict)

        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

    async def red_delete_data_for_user(self, **kwargs):
        return

    async def cog_unload(self):
        await self.session.close()

    @commands.command()
    @commands.cooldown(1, 8, commands.BucketType.user)
    @checks.bot_has_permissions(attach_files=True)
    @checks.bot_in_a_guild()
    async def imagine(self, ctx: commands.Context, *, prompt: str):
        """
        Generate an image

        **Arguments**
            - `prompt` a prompt to generate an image from
        """
        await self.generate_image(ctx, prompt)

    async def samplers_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = self.autocomplete_cache[interaction.guild_id].get("samplers")

        if not choices:
            await self._update_autocomplete_cache(interaction)

        if not choices:
            choices = AUTO_COMPLETE_SAMPLERS

        if not current:
            return [
                app_commands.Choice(name=choice, value=choice)
                for choice in choices[:24]
            ]
        else:
            choices = self.filter_list(choices, current)
            return [
                app_commands.Choice(name=choice, value=choice)
                for choice in choices[:24]
            ]

    async def loras_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = self.autocomplete_cache[interaction.guild_id].get("loras") or []

        if not choices:
            await self._update_autocomplete_cache(interaction)

        if current:
            choices = self.filter_list(choices, current)

        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices[:24]
        ]

    async def checkpoint_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = self.autocomplete_cache[interaction.guild_id].get("checkpoints") or []

        if not choices:
            await self._update_autocomplete_cache(interaction)

        if current:
            choices = self.filter_list(choices, current)

        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices[:24]
        ]

    @staticmethod
    def filter_list(options: list[str], filter: str):
        results = []

        ratios = [(item, fuzz.partial_ratio(filter.lower(), item.lower().removeprefix("<lora:"))) for item in options]

        sorted_options = sorted(ratios, key=lambda x: x[1], reverse=True)

        for item, _ in sorted_options:
            results.append(item)

        return results

    @app_commands.command(name="imagine")
    @app_commands.describe(
        prompt="The prompt to generate an image from",
        negative_prompt="The negative prompt to use",
        steps="The sampling steps to use",
        lora="Shortcut to get a LoRA to insert into a prompt",
        checkpoint="The checkpoint to use",
        cfg="The cfg to use",
        sampler="The sampler to use",
        seed="The seed to use",
    )
    @app_commands.autocomplete(
        sampler=samplers_autocomplete,
        lora=loras_autocomplete,
        checkpoint=checkpoint_autocomplete,
    )
    @app_commands.checks.cooldown(1, 8, key=None)
    @app_commands.checks.bot_has_permissions(attach_files=True)
    @app_commands.guild_only()
    async def imagine_app(
        self,
        interaction: discord.Interaction,
        prompt: str,
        negative_prompt: str = None,
        width: app_commands.Range[int, 256, 768] = None,
        height: app_commands.Range[int, 256, 768] = None,
        cfg: app_commands.Range[float, 1, 30] = None,
        steps: app_commands.Range[int, 1, 150] = None,
        sampler: str = None,
        seed: app_commands.Range[int, -1, None] = -1,
        checkpoint: str = None,
        lora: str = None
    ):
        """
        Generate an image using Stable Diffusion
        """
        await self.generate_image(interaction, prompt, lora, cfg, negative_prompt, steps, seed, sampler, width, height, checkpoint)
        asyncio.create_task(self._update_autocomplete_cache(interaction))

    async def _update_autocomplete_cache(self, interaction: discord.Interaction):
        guild = interaction.guild

        if not await self._check_endpoint_online(guild):
            return

        data = await self._fetch_data(guild, "samplers")
        if data:
            choices = [choice["name"] for choice in data]
            self.autocomplete_cache[guild.id]["samplers"] = choices
        data = await self._fetch_data(guild, "loras")
        if data:
            choices = [f"<lora:{choice['name']}:1>" for choice in data]
            self.autocomplete_cache[guild.id]["loras"] = choices
        data = await self._fetch_data(guild, "sd-models")
        if data:
            choices = [choice["model_name"] for choice in data]
            self.autocomplete_cache[guild.id]["checkpoints"] = choices
        logger.debug(
            f"Ran a update to get possible autocomplete terms in server {guild.id}")
