import base64
import io
import json
import logging
from typing import Union

import discord
from redbot.core import commands
from tenacity import retry, stop_after_attempt, wait_random

from aimage.abc import MixinMeta
from aimage.views import ImageActions

logger = logging.getLogger("red.bz_cogs.aimage")


class Functions(MixinMeta):
    async def generate_image(self,
                             context: Union[commands.Context, discord.Interaction],
                             prompt: str,
                             lora: str = None,
                             cfg: int = None,
                             negative_prompt: str = None,
                             steps: int = None,
                             seed: int = -1,
                             sampler: str = None,
                             payload: dict = None):

        if isinstance(context, discord.Interaction):
            await context.response.defer()
        else:
            await context.message.add_reaction("⏳")

        guild = context.guild

        endpoint, nsfw = await self._get_endpoint(guild)
        if not endpoint:
            return await self.sent_response(context, content=":warning: Endpoint not yet set for this server!")

        if await self._contains_blacklisted_word(guild, prompt):
            return self.sent_response(context, content=":warning: Prompt contains blacklisted words!")

        if lora:
            prompt = f"{lora} {prompt}"

        payload = payload or {
            "prompt": prompt,
            "cfg_scale": cfg or await self.config.guild(guild).cfg(),
            "negative_prompt": negative_prompt or await self.config.guild(guild).negative_prompt(),
            "steps": steps or await self.config.guild(guild).sampling_steps(),
            "seed": seed,
            "sampler_name": sampler or await self.config.guild(guild).sampler(),
        }

        if not nsfw:
            payload["script_name"] = "CensorScript"
            payload["script_args"] = [True, True]

        try:
            image_data, info_string, is_nsfw = await self._post_sd_endpoint(endpoint, payload)
        except:
            logger.exception("Failed request to Stable Diffusion endpoint")
            return await self.sent_response(context, content=":warning: Something went wrong!", ephemeral=True)

        user = context.user if isinstance(
            context, discord.Interaction) else context.author
        if is_nsfw:
            return await self.sent_response(context, content=f"🔞 {user.mention} generated a possible NSFW image with prompt: `{prompt}`", allowed_mentions=discord.AllowedMentions.none())

        await self.sent_response(context, file=discord.File(io.BytesIO(image_data), filename=f"image.png"), view=ImageActions(cog=self, image_info=info_string, payload=payload, author=user))

    async def sent_response(self, context: Union[commands.Context, discord.Interaction], **kwargs):
        if isinstance(context, discord.Interaction):
            return await context.followup.send(**kwargs)
        try:
            await context.message.remove_reaction("⏳", self.bot.user)
        except:
            pass
        await context.send(**kwargs)

    async def _get_endpoint(self, guild: discord.Guild):
        endpoint = await self.config.guild(guild).endpoint()
        nsfw = await self.config.guild(guild).nsfw()
        if not endpoint:
            endpoint = await self.config.endpoint()
            nsfw = await self.config.nsfw() and nsfw
        return endpoint, nsfw

    async def _contains_blacklisted_word(self, guild: discord.Guild, prompt: str):
        endpoint = await self.config.guild(guild).endpoint()
        if endpoint:
            blacklist = await self.config.guild(guild).words_blacklist()
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

    async def _fetch_data(self, guild: discord.Guild, endpoint_suffix: str):
        res = None
        try:
            endpoint, _ = await self._get_endpoint(guild)
            url = endpoint + endpoint_suffix
            async with self.session.get(url) as response:
                if response.status != 200:
                    response.raise_for_status()
                res = await response.json()
        except:
            logger.exception(
                f"Failed getting {endpoint_suffix} from Stable Diffusion endpoint in server {guild.id}")

        return res