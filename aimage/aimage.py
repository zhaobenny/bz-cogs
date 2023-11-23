import asyncio
import base64
import io
import json
import logging
from collections import defaultdict
from typing import List

import aiohttp
import discord
from redbot.core import Config, app_commands, checks, commands
from redbot.core.bot import Red
from tenacity import retry, stop_after_attempt, wait_random

from aimage.abc import CompositeMetaClass
from aimage.constants import (AUTO_COMPLETE_SAMPLERS,
                              DEFAULT_BADWORDS_BLACKLIST,
                              DEFAULT_NEGATIVE_PROMPT)
from aimage.settings import Settings
from aimage.views import ImageActions

logger = logging.getLogger("red.bz_cogs.aimage")


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
            "nsfw": True,
            "words_blacklist": DEFAULT_BADWORDS_BLACKLIST
        }

        default_guild = {
            "endpoint": None,
            "nsfw": True,
            "words_blacklist": DEFAULT_BADWORDS_BLACKLIST,
            "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
            "cfg": 7,
            "sampling_steps": 20,
            "sampler": "Euler a",
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
        Generate an image using Stable Diffusion

        **Arguments**
            - `prompt` a prompt to generate an image from
        """
        endpoint, nsfw = await self._get_endpoint(ctx)

        if not endpoint:
            return await ctx.send(":warning: Endpoint not yet set for this server!")

        if await self._contains_blacklisted_word(ctx, prompt):
            return await ctx.send(":warning: Prompt contains blacklisted words!")

        await ctx.react_quietly("⏳")

        payload = {
            "prompt": prompt,
            "cfg_scale": await self.config.guild(ctx.guild).cfg(),
            "negative_prompt": await self.config.guild(ctx.guild).negative_prompt(),
            "steps": await self.config.guild(ctx.guild).sampling_steps(),
            "sampler_name": await self.config.guild(ctx.guild).sampler()
        }

        if not nsfw:
            payload["script_name"] = "CensorScript"
            payload["script_args"] = [True, True]

        try:
            async with ctx.typing():
                image_data, info_string, is_nsfw = await self._post_sd_endpoint(endpoint, payload)
        except:
            logger.exception("Failed request to Stable Diffusion endpoint")
            return await ctx.react_quietly(":warning:")
        finally:
            await ctx.message.remove_reaction("⏳", ctx.me)

        if is_nsfw:
            return await ctx.send(f"🔞 {ctx.author.mention} generated a NSFW image with prompt: `{prompt}`", allowed_mentions=discord.AllowedMentions.none())

        await ctx.send(file=discord.File(io.BytesIO(image_data), filename=f"{ctx.message.id}.png"), view=ImageActions(image_info=info_string, bot=self.bot, author=ctx.author))
        await ctx.react_quietly("✅")

    async def samplers_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = self.autocomplete_cache[interaction.guild_id].get("samplers")

        if not choices:
            asyncio.create_task(self._update_autocomplete_cache(interaction))

        if not choices:
            choices = AUTO_COMPLETE_SAMPLERS

        if not current:
            return [
                app_commands.Choice(name=choice, value=choice)
                for choice in choices[:24]
            ]
        else:
            choices = [choice for choice in choices if current.lower()
                       in choice.lower()]
            return [
                app_commands.Choice(name=choice, value=choice)
                for choice in choices[:24]
            ]

    async def loras_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = self.autocomplete_cache[interaction.guild_id].get("loras") or [
        ]

        if not choices:
            asyncio.create_task(self._update_autocomplete_cache(interaction))

        if not (current.startswith("<lora:") and current.endswith(">")):
            current = "<lora:" + current
            choices = [choice for choice in choices if current.lower()
                       in choice.lower()]

        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices[:24]
        ]

    @app_commands.command(name="imagine")
    @app_commands.describe(
        prompt="The prompt to generate an image from",
        negative_prompt="The negative prompt to use",
        steps="The sampling steps to use",
        lora="Shortcut to get a LoRA to insert into a prompt",
        cfg="The cfg to use",
        sampler="The sampler to use",
        seed="The seed to use",
    )
    @app_commands.autocomplete(
        sampler=samplers_autocomplete,
        lora=loras_autocomplete
    )
    @app_commands.checks.cooldown(1, 8, key=None)
    @app_commands.checks.bot_has_permissions(attach_files=True)
    @app_commands.guild_only()
    async def imagine_app(
        self,
        interaction: discord.Interaction,
        prompt: str,
        negative_prompt: str = None,
        cfg: app_commands.Range[float, 1, 30] = None,
        steps: app_commands.Range[int, 1, 150] = None,
        sampler: str = None,
        seed: app_commands.Range[int, -1, None] = -1,
        lora: str = None
    ):
        """
        Generate an image using Stable Diffusion
        """
        ctx = await self.bot.get_context(interaction)

        endpoint, nsfw = await self._get_endpoint(ctx)
        if not endpoint:
            return await interaction.response.send_message(content=":warning: Endpoint not yet set for this server!")

        if await self._contains_blacklisted_word(ctx, prompt):
            return interaction.response.send_message(":warning: Prompt contains blacklisted words!")

        if lora:
            prompt = f"{lora} {prompt}"

        await interaction.response.defer()

        payload = {
            "prompt": prompt,
            "cfg_scale": cfg or await self.config.guild(ctx.guild).cfg(),
            "negative_prompt": negative_prompt or await self.config.guild(ctx.guild).negative_prompt(),
            "steps": steps or await self.config.guild(ctx.guild).sampling_steps(),
            "seed": seed,
            "sampler_name": sampler or await self.config.guild(ctx.guild).sampler(),
        }

        if not nsfw:
            payload["script_name"] = "CensorScript"
            payload["script_args"] = [True, True]

        try:
            image_data, info_string, is_nsfw = await self._post_sd_endpoint(endpoint, payload)
        except:
            logger.exception("Failed request to Stable Diffusion endpoint")
            return await interaction.followup.send(content=":warning: Something went wrong!", ephemeral=True)

        if is_nsfw:
            return await interaction.followup.send(content=f"🔞 {interaction.user.mention} generated a NSFW image with prompt: `{prompt}`", allowed_mentions=discord.AllowedMentions.none())

        await interaction.followup.send(file=discord.File(io.BytesIO(image_data), filename=f"image.png"), view=ImageActions(image_info=info_string, bot=self.bot, author=ctx.author))
        asyncio.create_task(self._update_autocomplete_cache(interaction))

    async def _get_endpoint(self, ctx):
        endpoint = await self.config.guild(ctx.guild).endpoint()
        nsfw = await self.config.guild(ctx.guild).nsfw()
        if not endpoint:
            endpoint = await self.config.endpoint()
            nsfw = await self.config.nsfw() and nsfw
        return endpoint, nsfw

    async def _contains_blacklisted_word(self, ctx, prompt):
        endpoint = await self.config.guild(ctx.guild).endpoint()
        if endpoint:
            blacklist = await self.config.guild(ctx.guild).words_blacklist()
        else:
            blacklist = await self.config.words_blacklist()

        if any(word in prompt.lower() for word in blacklist):
            return True
        return False

    @retry(wait=wait_random(min=2, max=5), stop=stop_after_attempt(2), reraise=True)
    async def _post_sd_endpoint(self, endpoint, payload):
        url = endpoint + "txt2img"
        async with self.session.post(url=url, json=payload) as response:
            if response.status != 200:
                response.raise_for_status()
            r = await response.json()
            image_data = base64.b64decode(r["images"][0])

            # a1111 shenanigans
            info = json.loads(r["info"])
            info_string = info.get("infotexts")[0]
            try:
                is_nsfw = info.get("extra_generation_params",
                                   {}).get("nsfw", [])[0]
                if is_nsfw:
                    # try to save you from cold boot attack
                    del r["images"]
                    r["images"] = []
                    del image_data
                    image_data = ""
            except IndexError:
                is_nsfw = False

            if logger.isEnabledFor(logging.DEBUG):
                del r["images"]
                logger.debug(
                    f"Requested with parameters: {json.dumps(r, indent=4)}")

        return image_data, info_string, is_nsfw

    async def _update_autocomplete_cache(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        data = await self._fetch_data(interaction, "samplers")
        if data:
            choices = [choice["name"] for choice in data]
            self.autocomplete_cache[guild_id]["samplers"] = choices
        data = await self._fetch_data(interaction, "loras")
        if data:
            choices = [f"<lora:{choice['name']}:1>" for choice in data]
            self.autocomplete_cache[guild_id]["loras"] = choices
        logger.debug(
            f"Ran a update to get possible autocomplete terms in server {guild_id}")

    async def _fetch_data(self, interaction: discord.Interaction, endpoint_suffix: str):
        res = None
        try:
            endpoint, _ = await self._get_endpoint(interaction)
            url = endpoint + endpoint_suffix
            async with self.session.get(url) as response:
                if response.status != 200:
                    response.raise_for_status()
                res = await response.json()
        except:
            logger.exception(
                f"Failed getting {endpoint_suffix} from Stable Diffusion endpoint in server {interaction.guild_id}")

        return res
