import asyncio
import base64
import io
import json
import logging
import random
from enum import Enum
from typing import Union

import aiohttp
import discord
from redbot.core import commands
from tenacity import retry, stop_after_attempt, wait_random

from aimage.abc import MixinMeta
from aimage.common.constants import ADETAILER_ARGS, TILED_VAE_ARGS
from aimage.common.helpers import delete_button_after, get_auth, send_response
from aimage.common.params import ImageGenParams
from aimage.common.response import ImageResponse
from aimage.views.image_actions import ImageActions

logger = logging.getLogger("red.bz_cogs.aimage")


class ImageGenerationType(Enum):
    TXT2IMG = "txt2img"
    IMG2IMG = "img2img"


class ImageHandler(MixinMeta):
    def __init__(self):
        super().__init__()

    async def _get_endpoint(self, guild: discord.Guild):
        return await self.config.guild(guild).endpoint()

    async def _get_auth(self, guild: discord.Guild):
        return get_auth(await self.config.guild(guild).auth())

    async def generate_image(
        self,
        context: Union[commands.Context, discord.Interaction],
        params: ImageGenParams,
    ):
        payload = await self._generate_payload(context.guild, params)
        await self._execute_image_generation(
            context, params, payload, ImageGenerationType.TXT2IMG
        )

    async def generate_img2img(
        self, context: discord.Interaction, params: ImageGenParams
    ):
        init_image = params.init_image if params.init_image else None
        payload = await self._generate_payload(context.guild, params, init_image)
        await self._execute_image_generation(
            context, params, payload, ImageGenerationType.IMG2IMG
        )

    async def _execute_image_generation(
        self,
        context: Union[commands.Context, discord.Interaction],
        params: ImageGenParams,
        payload: dict,
        generation_type: ImageGenerationType,
    ):
        if not isinstance(context, discord.Interaction):
            await context.message.add_reaction("⏳")

        guild = context.guild
        user = (
            context.user if isinstance(context, discord.Interaction) else context.author
        )

        if self.generating[user.id]:
            content = ":warning: You must wait for your current image to finish generating before you can request a new one."
            return await send_response(context, content=content, ephemeral=True)

        if await self._contains_blacklisted_word(guild, params.prompt):
            return await send_response(
                context, content=":warning: Prompt contains blacklisted words!"
            )

        try:
            self.generating[user.id] = True
            response: ImageResponse = await self._post_image_gen(
                guild, payload, generation_type
            )
        except ValueError as error:
            return await send_response(
                context, content=f":warning: Invalid parameter: {error}", ephemeral=True
            )
        except aiohttp.ClientResponseError:
            logger.exception(f"Failed request in host {guild.id}")
            return await send_response(
                context,
                content=":warning: Timed out! Bad response from host!",
                ephemeral=True,
            )
        except aiohttp.ClientConnectorError:
            logger.exception(f"Failed request in server {guild.id}")
            return await send_response(
                context,
                content=":warning: Timed out! Could not reach host!",
                ephemeral=True,
            )
        except Exception:
            logger.exception(f"Failed request in server {guild.id}")
            return await send_response(
                context, content=":warning: Something went wrong!", ephemeral=True
            )
        finally:
            self.generating[user.id] = False

        if (
            response.is_nsfw
            and not await self.config.guild(guild).nsfw()
            and not await self.config.guild(guild).nsfw_blurred()
        ):
            return await send_response(
                context,
                content=f"🔞 {user.mention} generated a possible NSFW image with prompt: `{params.prompt}`",
                allowed_mentions=discord.AllowedMentions.none(),
            )

        maxsize = await self.config.guild(context.guild).max_img2img()
        file = discord.File(
            io.BytesIO(response.data), filename=f"image.{response.extension}"
        )
        view = ImageActions(
            self, response.info_string, response.payload, user, context.channel, maxsize
        )
        msg = await send_response(context, file=file, view=view)
        asyncio.create_task(delete_button_after(msg))

        if random.random() > 0.51:  # update only half the time
            asyncio.create_task(self._update_autocomplete_cache(context))

        imagescanner = self.bot.get_cog("ImageScanner")
        if imagescanner and response.extension == "png":
            if context.channel.id in imagescanner.scan_channels:
                imagescanner.image_cache[msg.id] = (
                    {0: response.info_string},
                    {0: response.data},
                )
                await msg.add_reaction("🔎")

    async def _generate_payload(
        self, guild: discord.Guild, params: ImageGenParams, init_image: bytes = None
    ) -> dict:
        payload = {
            "prompt": f"{params.prompt} {params.lora}",
            "negative_prompt": params.negative_prompt
            or await self.config.guild(guild).negative_prompt(),
            "styles": params.style.split(", ") if params.style else [],
            "cfg_scale": params.cfg or await self.config.guild(guild).cfg(),
            "steps": params.steps or await self.config.guild(guild).sampling_steps(),
            "seed": params.seed,
            "subseed": params.variation_seed,
            "subseed_strength": params.variation,
            "sampler_name": params.sampler or await self.config.guild(guild).sampler(),
            "override_settings": {
                "sd_model_checkpoint": params.checkpoint
                or await self.config.guild(guild).checkpoint(),
                "sd_vae": params.vae or await self.config.guild(guild).vae(),
            },
            "width": params.width or await self.config.guild(guild).width(),
            "height": params.height or await self.config.guild(guild).height(),
            "alwayson_scripts": {},
        }

        if init_image:
            payload.update(
                {
                    "init_images": [base64.b64encode(init_image).decode("utf8")],
                    "denoising_strength": params.denoising,
                }
            )

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
    async def _post_image_gen(
        self, guild: discord.Guild, payload: dict, generation_type: ImageGenerationType
    ):
        endpoint = await self._get_endpoint(guild)
        auth = await self._get_auth(guild)
        url = endpoint + generation_type.value
        async with self.session.post(url=url, json=payload, auth=auth) as response:
            r = await response.json()
            if response.status == 422:
                raise ValueError(r["detail"])
            elif response.status != 200:
                response.raise_for_status()
            data = base64.b64decode(r["images"][0])

            info = json.loads(r["info"])
            info_string = info.get("infotexts")[0]
            try:
                is_nsfw = info.get("extra_generation_params", {}).get("nsfw", [])[0]
            except IndexError:
                is_nsfw = False

            if logger.isEnabledFor(logging.DEBUG):
                del r["images"]
                logger.debug(f"Requested with parameters: {json.dumps(r, indent=4)}")

        return ImageResponse(
            data=data, info_string=info_string, is_nsfw=is_nsfw, payload=payload
        )

    async def _update_autocomplete_cache(
        self, ctx: Union[commands.Context, discord.Interaction]
    ):
        cache_mapping = {
            "upscalers": "upscalers",
            "scripts": "scripts",
            "loras": "loras",
            "sd-models": "checkpoints",
            "sd-vae": "vaes",
            "samplers": "samplers",
            "prompt-styles": "styles",
        }
        for page, cache_key in cache_mapping.items():
            try:
                data = await self._get_terms(ctx.guild, page)
            except Exception as e:
                logger.warning(
                    f"Failed to update autocomplete cache for {cache_key} in {ctx.guild.id}: \n {e}"
                )
                continue

            if page == "scripts":
                choices = [choice for choice in data["txt2img"]] if data else []
            elif page == "loras":
                choices = [choice["name"] for choice in data] if data else []
            elif page in ["sd-models", "sd-vae"]:
                choices = [choice["model_name"] for choice in data] if data else []
            else:
                choices = [choice["name"] for choice in data] if data else []

            self.autocomplete_cache[ctx.guild.id][cache_key] = choices

    @retry(wait=wait_random(min=3, max=5), stop=stop_after_attempt(1), reraise=True)
    async def _get_terms(self, guild: discord.Guild, page: str):
        endpoint = await self._get_endpoint(guild)
        auth = await self._get_auth(guild)
        url = endpoint + page
        async with self.session.get(
            url=url, auth=auth, raise_for_status=True
        ) as response:
            return await response.json()

    async def _contains_blacklisted_word(self, guild: discord.Guild, prompt: str):
        blacklist = await self.config.guild(guild).words_blacklist()
        return any(word in prompt.lower() for word in blacklist)
