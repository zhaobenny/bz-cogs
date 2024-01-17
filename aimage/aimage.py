import asyncio
import logging
from collections import defaultdict
from typing import List, Union
from copy import copy

import aiohttp
import discord
from rapidfuzz import fuzz
from redbot.core import Config, app_commands, checks, commands
from redbot.core.bot import Red

from aimage.abc import CompositeMetaClass
from aimage.constants import DEFAULT_BADWORDS_BLACKLIST, DEFAULT_NEGATIVE_PROMPT
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
            "vae": None,
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
        asyncio.create_task(self._update_autocomplete_cache(ctx))
        await self.generate_image(ctx, prompt=prompt)

    async def object_autocomplete(self, interaction: discord.Interaction, current: str, object_type: str) -> List[app_commands.Choice[str]]:
        choices = self.autocomplete_cache[interaction.guild_id].get(object_type) or []

        if not choices:
            await self._update_autocomplete_cache(interaction)

        if current:
            choices = self.filter_list(choices, current)

        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices[:25]
        ]

    async def samplers_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self.object_autocomplete(interaction, current, "samplers")

    async def loras_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self.object_autocomplete(interaction, current, "loras")

    async def checkpoint_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self.object_autocomplete(interaction, current, "checkpoints")

    async def vae_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return await self.object_autocomplete(interaction, current, "vaes")

    @staticmethod
    def filter_list(options: list[str], current: str):
        results = []

        ratios = [(item, fuzz.partial_ratio(current.lower(), item.lower().removeprefix("<lora:"))) for item in options]

        sorted_options = sorted(ratios, key=lambda x: x[1], reverse=True)

        for item, _ in sorted_options:
            results.append(item)

        return results

    @app_commands.command(name="imagine")
    @app_commands.describe(
        prompt="The prompt to generate an image from.",
        negative_prompt="Undesired terms go here.",
        width="Default image width is 512, or 1024 for SDXL.",
        height="Default image height is 512, or 1024 for SDXL.",
        cfg="Sets the intensity of the prompt, 7 is common.",
        sampler="The algorithm which guides image generation.",
        steps="How many sampling steps, 20-30 is common.",
        seed="Random number that generates the image, -1 for random.",
        variation="Finetunes details within the same seed, 0.05 is common.",
        variation_seed="This subseed guides the variation, -1 for random.",
        checkpoint="The main AI model used to generate the image.",
        vae="The VAE converts the final details of the image.",
        lora="Shortcut to insert a LoRA into the prompt.",
    )
    @app_commands.autocomplete(
        sampler=samplers_autocomplete,
        lora=loras_autocomplete,
        checkpoint=checkpoint_autocomplete,
        vae=vae_autocomplete,
    )
    @app_commands.checks.cooldown(1, 8, key=None)
    @app_commands.checks.bot_has_permissions(attach_files=True)
    @app_commands.guild_only()
    async def imagine_app(
        self,
        interaction: discord.Interaction,
        prompt: str,
        negative_prompt: str = None,
        width: app_commands.Range[int, 256, 1536] = None,
        height: app_commands.Range[int, 256, 1536] = None,
        cfg: app_commands.Range[float, 1, 30] = None,
        sampler: str = None,
        steps: app_commands.Range[int, 1, 150] = None,
        seed: app_commands.Range[int, -1, None] = -1,
        variation: app_commands.Range[float, 0, 1] = 0,
        variation_seed: app_commands.Range[int, -1, None] = -1,
        checkpoint: str = None,
        vae: str = None,
        lora: str = None
    ):
        """
        Generate an image using Stable Diffusion.
        """
        ctx: commands.Context = await self.bot.get_context(interaction)
        if not await self._can_run_command(ctx, "imagine"):
            return await interaction.response.send_message("You do not have permission to do this.", ephemeral=True)

        asyncio.create_task(self._update_autocomplete_cache(interaction))
        await self.generate_image(interaction,
                                  prompt=prompt, negative_prompt=negative_prompt,
                                  width=width, height=height, cfg=cfg, sampler=sampler, steps=steps,
                                  seed=seed, subseed=variation_seed, subseed_strength=variation,
                                  checkpoint=checkpoint, vae=vae, lora=lora)

    async def _can_run_command(self, ctx: commands.Context, command_name: str) -> bool:
        prefix = await self.bot.get_prefix(ctx.message)
        prefix = prefix[0] if isinstance(prefix, list) else prefix
        fake_message = copy(ctx.message)
        fake_message.content = prefix + command_name
        command = ctx.bot.get_command(command_name)
        fake_context: commands.Context = await ctx.bot.get_context(fake_message)  # noqa
        try:
            can = await command.can_run(fake_context, check_all_parents=True, change_permission_state=False)
        except commands.CommandError:
            can = False
        return can

    async def _update_autocomplete_cache(self, ctx: Union[commands.Context, discord.Interaction]):
        guild = ctx.guild

        if not await self._check_endpoint_online(guild):
            return

        if data := await self._fetch_data(guild, "upscalers"):
            choices = [choice["name"] for choice in data]
            self.autocomplete_cache[guild.id]["upscalers"] = choices

        if data := await self._fetch_data(guild, "loras"):
            choices = [f"<lora:{choice['name']}:1>" for choice in data]
            self.autocomplete_cache[guild.id]["loras"] = choices

        if data := await self._fetch_data(guild, "sd-models"):
            choices = [choice["model_name"] for choice in data]
            self.autocomplete_cache[guild.id]["checkpoints"] = choices

        if data := await self._fetch_data(guild, "sd-vae"):
            choices = [choice["model_name"] for choice in data]
            self.autocomplete_cache[guild.id]["vaes"] = choices

        if data := await self._fetch_data(guild, "samplers"):
            choices = [choice["name"] for choice in data]
            self.autocomplete_cache[guild.id]["samplers"] = choices

        logger.debug(
            f"Ran a update to get possible autocomplete terms in server {guild.id}")
