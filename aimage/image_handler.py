import asyncio
import base64
import io
import json
import logging
import random
from typing import Union

import aiohttp
import discord
from redbot.core import commands
from tenacity import retry, stop_after_attempt, wait_random

from aimage.abc import MixinMeta
from aimage.common.constants import (A1111_SAMPLERS, ADETAILER_ARGS,
                                     CACHE_MAPPING, TILED_VAE_ARGS)
from aimage.common.helpers import (delete_button_after, get_auth,
                                     send_response)
from aimage.common.params import ImageGenParams
from aimage.types import ImageGenerationType, ImageResponse
from aimage.views.image_actions import ImageActions

logger = logging.getLogger("red.bz_cogs.aimage")




class ImageHandler(MixinMeta):
    async def _execute_image_generation(self, context: Union[commands.Context, discord.Interaction],
                                        params: ImageGenParams = None,
                                        payload: dict = None,
                                        image_generation_type: ImageGenerationType = ImageGenerationType.TXT2IMG):

        if not isinstance(context, discord.Interaction):
            await context.message.add_reaction("⏳")

        guild = context.guild
        user = context.user if isinstance(context, discord.Interaction) else context.author

        if self.generating[user.id]:
            content = ":warning: You must wait for your current image to finish generating before you can request a new one."
            return await send_response(context, content=content, ephemeral=True)

        prompt = params.prompt if params else payload.get("prompt", "")

        if await self._contains_blacklisted_word(guild, prompt):
            return await send_response(context, content=":warning: Prompt contains blacklisted words!")

        try:
            self.generating[user.id] = True

            endpoint = await self.config.guild(guild).endpoint()
            auth = get_auth(await self.config.guild(guild).auth())

            if not payload:
                if image_generation_type == ImageGenerationType.IMG2IMG:
                    init_image = params.init_image
                else:
                    init_image = None
                payload = await self._generate_payload(guild, params, init_image)

            response: ImageResponse = await self._post_image_gen(endpoint, auth, payload, image_generation_type)

        except ValueError as error:
            return await send_response(context, content=f":warning: Invalid parameter: {error}", ephemeral=True)
        except aiohttp.ClientResponseError as error:
            logger.exception(f"Failed request in host {guild.id}")
            return await send_response(context, content=":warning: Timed out! Bad response from host!", ephemeral=True)
        except aiohttp.ClientConnectorError:
            logger.exception(f"Failed request in server {guild.id}")
            return await send_response(context, content=":warning: Timed out! Could not reach host!", ephemeral=True)
        except Exception:
            logger.exception(f"Failed request in server {guild.id}")
            return await send_response(context, content=":warning: Something went wrong!", ephemeral=True)
        finally:
            self.generating[user.id] = False

        if response.is_nsfw and not await self.config.guild(guild).nsfw() and not await self.config.guild(guild).nsfw_blurred():
            return await send_response(context, content=f"🔞 {user.mention} generated a possible NSFW image with prompt: `{prompt}`", allowed_mentions=discord.AllowedMentions.none())

        maxsize = await self.config.guild(context.guild).max_img2img()
        file = discord.File(io.BytesIO(response.data), filename=f"image.{response.extension}")
        view = ImageActions(self, response.info_string, response.payload, user, context.channel, maxsize)
        msg = await send_response(context, file=file, view=view)
        asyncio.create_task(delete_button_after(msg))

        if (random.random() > 0.51):  # update only half the time
            asyncio.create_task(self._update_autocomplete_cache(context))

        imagescanner = self.bot.get_cog("ImageScanner")
        if imagescanner and response.extension == "png":
            if context.channel.id in imagescanner.scan_channels:
                imagescanner.image_cache[msg.id] = (
                    {0: response.info_string}, {0: response.data})
                await msg.add_reaction("🔎")

    async def generate_image(self, context: Union[commands.Context, discord.Interaction],
                             params: ImageGenParams = None,
                             payload: dict = None):
        await self._execute_image_generation(context, params=params, payload=payload, image_generation_type=ImageGenerationType.TXT2IMG)

    async def generate_img2img(self, context: discord.Interaction,
                               params: ImageGenParams = None,
                               payload: dict = None):
        await self._execute_image_generation(context, params=params, payload=payload, image_generation_type=ImageGenerationType.IMG2IMG)

    async def _contains_blacklisted_word(self, guild: discord.Guild, prompt: str):
        blacklist = await self.config.guild(guild).words_blacklist()
        return any(word in prompt.lower() for word in blacklist)

    async def _update_autocomplete_cache(self, ctx: Union[commands.Context, discord.Interaction]):
        guild = ctx.guild
        endpoint = await self.config.guild(guild).endpoint()
        if not endpoint:
            return
        auth = get_auth(await self.config.guild(guild).auth())

        if not self.autocomplete_cache.get(guild.id, {}).get("samplers"):
            self.autocomplete_cache[guild.id] = {"samplers": A1111_SAMPLERS}

        logger.debug(
            f"Ran a update to get possible autocomplete terms in server {guild.id}")
        for page, cache_key in CACHE_MAPPING.items():
            try:
                data = await self._get_terms(endpoint, auth, page)
            except Exception as e:
                logger.warning(
                    f"Failed to update autocomplete cache for {cache_key} in {guild.id}: \n {e}")
                continue

            if page == "scripts":
                choices = [choice for choice in data["txt2img"]] if data else []
            elif page == "loras":
                choices = [choice['name'] for choice in data] if data else []
            elif page in ["sd-models", "sd-vae"]:
                choices = [choice["model_name"]
                           for choice in data] if data else []
            else:
                choices = [choice["name"] for choice in data] if data else []

            self.autocomplete_cache[guild.id][cache_key] = choices

    async def _generate_payload(self, guild: discord.Guild, params: ImageGenParams, init_image: bytes = None) -> dict:
        payload = {
            "prompt": f"{params.prompt} {params.lora}",
            "negative_prompt": params.negative_prompt or await self.config.guild(guild).negative_prompt(),
            "styles": params.style.split(", ") if params.style else [],
            "cfg_scale": params.cfg or await self.config.guild(guild).cfg(),
            "steps": params.steps or await self.config.guild(guild).sampling_steps(),
            "seed": params.seed,
            "subseed": params.subseed,
            "subseed_strength": params.subseed_strength,
            "sampler_name": params.sampler or await self.config.guild(guild).sampler(),
            "scheduler": params.scheduler or "Automatic",
            "override_settings": {
                "sd_model_checkpoint": params.checkpoint or await self.config.guild(guild).checkpoint(),
                "sd_vae": params.vae or await self.config.guild(guild).vae()
            },
            "width": params.width or await self.config.guild(guild).width(),
            "height": params.height or await self.config.guild(guild).height(),
            "alwayson_scripts": {}
        }

        # force flux support for now
        if payload.get("override_settings", {}).get("sd_model_checkpoint") and "flux" in payload["override_settings"]["sd_model_checkpoint"]:
            logger.debug(
                "Flux model detected, setting scheduler to Simple and cfg_scale to 1")
            payload["scheduler"] = "Simple"
            payload["cfg_scale"] = 1

        if init_image:
            payload.update({
                "init_images": [base64.b64encode(init_image).decode("utf8")],
                "denoising_strength": params.denoising
            })

        if await self.config.guild(guild).adetailer():
            payload["alwayson_scripts"].update(ADETAILER_ARGS)

        if await self.config.guild(guild).tiledvae():
            payload["alwayson_scripts"].update(TILED_VAE_ARGS)

        if not (await self.config.guild(guild).nsfw()):
            sensitivity = await self.config.guild(guild).nsfw_sensitivity()
            payload["script_name"] = "CensorScript"
            payload["script_args"] = [True, True, sensitivity]

        return payload

    @retry(wait=wait_random(min=3, max=5), stop=stop_after_attempt(3), reraise=True)
    async def _post_image_gen(self, endpoint: str, auth, payload, generation_type: ImageGenerationType):
        url = endpoint + generation_type.value
        async with self.session.post(url=url, json=payload, auth=auth) as response:
            r = await response.json()
            if response.status == 422:
                raise ValueError(r.get("detail", "Unknown error"))
            elif response.status != 200:
                response.raise_for_status()
            data = base64.b64decode(r["images"][0])

            # a1111 shenanigans
            info = json.loads(r["info"])
            info_string = info.get("infotexts")[0]
            try:
                is_nsfw = info.get(
                    "extra_generation_params", {}).get("nsfw", [])[0]
            except IndexError:
                is_nsfw = False

            if logger.isEnabledFor(logging.DEBUG):
                del r["images"]
                logger.debug(
                    f"Requested with parameters: {json.dumps(r, indent=4)}")

        return ImageResponse(data=data, info_string=info_string, is_nsfw=is_nsfw, payload=payload)

    @retry(wait=wait_random(min=3, max=5), stop=stop_after_attempt(1), reraise=True)
    async def _get_terms(self, endpoint: str, auth: aiohttp.BasicAuth, page: str):
        url = endpoint + page
        async with self.session.get(url=url, auth=auth, raise_for_status=True) as response:
            return await response.json()
