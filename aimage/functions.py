import asyncio
import base64
import io
import json
import logging
from typing import Union

import aiohttp
import discord
from redbot.core import commands
from tenacity import retry, stop_after_attempt, wait_random

from aimage.abc import MixinMeta
from aimage.constants import ADETAILER_ARGS, TILED_VAE_ARGS
from aimage.helpers import delete_button_after, get_auth, round_to_nearest
from aimage.stablehordeapi import StableHordeAPI
from aimage.views import ImageActions

logger = logging.getLogger("red.bz_cogs.aimage")


class Functions(MixinMeta):
    async def generate_image(self,
                             context: Union[commands.Context, discord.Interaction],
                             payload: dict = None,
                             prompt: str = "",
                             negative_prompt: str = None,
                             width: int = None,
                             height: int = None,
                             cfg: int = None,
                             sampler: str = None,
                             steps: int = None,
                             seed: int = -1,
                             subseed: int = -1,
                             subseed_strength: float = 0,
                             checkpoint: str = None,
                             vae: str = None,
                             lora: str = ""):

        if not isinstance(context, discord.Interaction):
            await context.message.add_reaction("⏳")

        guild = context.guild
        user = context.user if isinstance(context, discord.Interaction) else context.author

        if self.generating[user.id]:
            content = ":warning: You must wait for your current image to finish generating before you can request a new one."
            return await self.send_response(context, content=content, ephemeral=True)

        endpoint, auth_str, nsfw = await self._get_endpoint(guild)
        if not endpoint:
            return await self.send_response(context, content=":warning: Endpoint not yet set for this server!")

        if await self._contains_blacklisted_word(guild, prompt):
            return await self.send_response(context, content=":warning: Prompt contains blacklisted words!")

        payload = payload or {
            "prompt": prompt + " " + lora,
            "cfg_scale": cfg or await self.config.guild(guild).cfg(),
            "negative_prompt": negative_prompt or await self.config.guild(guild).negative_prompt(),
            "steps": steps or await self.config.guild(guild).sampling_steps(),
            "seed": seed,
            "subseed": subseed,
            "subseed_strength": subseed_strength,
            "sampler_name": sampler or await self.config.guild(guild).sampler(),
            "override_settings": {
                "sd_model_checkpoint": checkpoint or await self.config.guild(guild).checkpoint(),
                "sd_vae": vae or await self.config.guild(guild).vae()
            },
            "width": width or await self.config.guild(guild).width(),
            "height": height or await self.config.guild(guild).height(),
            "alwayson_scripts": {}
        }

        if await self.config.guild(guild).adetailer():
            payload["alwayson_scripts"].update(ADETAILER_ARGS)
        if await self.config.guild(guild).tiledvae():
            payload["alwayson_scripts"].update(TILED_VAE_ARGS)

        if not nsfw:
            payload["script_name"] = "CensorScript"
            payload["script_args"] = [True, True]

        try:
            self.generating[user.id] = True
            image_data, info_string, is_nsfw = await self._post_sd_endpoint(endpoint + "txt2img", payload, auth_str)
            image_extension = "png"
        except Exception as error:
            if await self.config.aihorde():
                aihorde_result = await self._request_aihorde(context, nsfw, payload)
                if isinstance(aihorde_result, discord.Message):
                    return
                image_data, info_string, is_nsfw = aihorde_result
                image_extension = ".webp"
            else:
                if isinstance(error, aiohttp.ClientConnectorError):
                    return await self.send_response(context, content=":warning: Timed out! Server is offline.", ephemeral=True)
                else:
                    logger.exception(f"Failed request to Stable Diffusion endpoint in server {guild.id}")
                    return await self.send_response(context, content=":warning: Something went wrong!", ephemeral=True)
        finally:
            self.generating[user.id] = False

        if is_nsfw:
            return await self.send_response(context, content=f"🔞 {user.mention} generated a possible NSFW image with prompt: `{prompt}`", allowed_mentions=discord.AllowedMentions.none())

        file = discord.File(io.BytesIO(image_data), filename=f"image.{image_extension}")
        view = ImageActions(self, info_string, payload, user, context.channel)
        msg = await self.send_response(context, file=file, view=view)
        asyncio.create_task(delete_button_after(msg))

        imagescanner = self.bot.get_cog("ImageScanner")
        if imagescanner and image_extension == "png":
            if context.channel.id in imagescanner.scan_channels:  # noqa
                imagescanner.image_cache[msg.id] = ({1: info_string}, {1: image_data})  # noqa
                await msg.add_reaction("🔎")

    async def generate_img2img(self,
                               context: discord.Interaction,
                               payload: dict = None,
                               prompt: str = "",
                               negative_prompt: str = None,
                               width: int = None,
                               height: int = None,
                               cfg: int = None,
                               sampler: str = None,
                               steps: int = None,
                               seed: int = -1,
                               subseed: int = -1,
                               subseed_strength: float = 0,
                               checkpoint: str = None,
                               vae: str = None,
                               lora: str = "",
                               image: bytes = None,
                               denoising: float = None,
                               scale: float = 1):
        guild = context.guild
        user = context.user

        if self.generating[user.id]:
            content = ":warning: You must wait for your current image to finish generating before you can request a new one."
            return await self.send_response(context, content=content, ephemeral=True)

        endpoint, auth_str, nsfw = await self._get_endpoint(guild)
        if not endpoint:
            return await self.send_response(context, content=":warning: Endpoint not yet set for this server!")

        if await self._contains_blacklisted_word(guild, prompt):
            return await self.send_response(context, content=":warning: Prompt contains blacklisted words!")

        payload = payload or {
            "prompt": prompt + " " + lora,
            "cfg_scale": cfg or await self.config.guild(guild).cfg(),
            "negative_prompt": negative_prompt or await self.config.guild(guild).negative_prompt(),
            "steps": steps or await self.config.guild(guild).sampling_steps(),
            "seed": seed,
            "subseed": subseed,
            "subseed_strength": subseed_strength,
            "sampler_name": sampler or await self.config.guild(guild).sampler(),
            "override_settings": {
                "sd_model_checkpoint": checkpoint or await self.config.guild(guild).checkpoint(),
                "sd_vae": vae or await self.config.guild(guild).vae()
            },
            "width": int(scale * width),
            "height": int(scale * height),
            "init_images": [base64.b64encode(image).decode("utf8")],
            "denoising_strength": denoising,
            "alwayson_scripts": {}
        }

        if await self.config.guild(guild).adetailer():
            payload["alwayson_scripts"].update(ADETAILER_ARGS)
        if await self.config.guild(guild).tiledvae():
            payload["alwayson_scripts"].update(TILED_VAE_ARGS)

        if not nsfw:
            payload["script_name"] = "CensorScript"
            payload["script_args"] = [True, True]

        try:
            self.generating[user.id] = True
            image_data, info_string, is_nsfw = await self._post_sd_endpoint(endpoint + "img2img", payload, auth_str)
            image_extension = "png"
        except Exception as error:
            if isinstance(error, aiohttp.ClientConnectorError):
                return await self.send_response(context, content=":warning: Timed out! Server is offline.", ephemeral=True)
            else:
                logger.exception(f"Failed request to Stable Diffusion endpoint in server {guild.id}")
                return await self.send_response(context, content=":warning: Something went wrong!", ephemeral=True)
        finally:
            self.generating[user.id] = False

        if is_nsfw:
            return await self.send_response(context, content=f"🔞 {user.mention} generated a possible NSFW image with prompt: `{prompt}`", allowed_mentions=discord.AllowedMentions.none())

        file = discord.File(io.BytesIO(image_data), filename=f"image.{image_extension}")
        view = ImageActions(self, info_string, payload, user, context.channel)
        msg = await self.send_response(context, file=file, view=view)
        asyncio.create_task(delete_button_after(msg))

        imagescanner = self.bot.get_cog("ImageScanner")
        if imagescanner and image_extension == "png":
            if context.channel.id in imagescanner.scan_channels:  # noqa
                imagescanner.image_cache[msg.id] = ({1: info_string}, {1: image_data})  # noqa
                await msg.add_reaction("🔎")

    async def send_response(self, context: Union[commands.Context, discord.Interaction], **kwargs) -> discord.Message:
        if isinstance(context, discord.Interaction):
            return await context.followup.send(**kwargs)
        else:
            try:
                await context.message.remove_reaction("⏳", self.bot.user)
            except:
                pass
            return await context.send(**kwargs)

    async def _get_endpoint(self, guild: discord.Guild):
        endpoint: str = await self.config.guild(guild).endpoint()
        auth: str = await self.config.guild(guild).auth()
        nsfw: bool = await self.config.guild(guild).nsfw()
        if not endpoint:
            endpoint = await self.config.endpoint()
            auth = await self.config.auth()
            nsfw = await self.config.nsfw() and nsfw
        return endpoint, auth, nsfw

    async def _contains_blacklisted_word(self, guild: discord.Guild, prompt: str):
        endpoint = await self.config.guild(guild).endpoint()
        if endpoint:
            blacklist = await self.config.guild(guild).words_blacklist()
        else:
            blacklist = await self.config.words_blacklist()

        if any(word in prompt.lower() for word in blacklist):
            return True
        return False

    @retry(wait=wait_random(min=2, max=3), stop=stop_after_attempt(2), reraise=True)
    async def _post_sd_endpoint(self, endpoint, payload, auth_str):
        async with self.session.post(url=endpoint, json=payload, auth=get_auth(auth_str)) as response:
            if response.status != 200:
                response.raise_for_status()
            r = await response.json()
            image_data = base64.b64decode(r["images"][0])

            # a1111 shenanigans
            info = json.loads(r["info"])
            info_string = info.get("infotexts")[0]
            try:
                is_nsfw = info.get("extra_generation_params", {}).get("nsfw", [])[0]
            except IndexError:
                is_nsfw = False

            if logger.isEnabledFor(logging.DEBUG):
                del r["images"]
                logger.debug(f"Requested with parameters: {json.dumps(r, indent=4)}")

        return image_data, info_string, is_nsfw

    async def _request_aihorde(self, context: Union[commands.Context, discord.Interaction], is_allowed_nsfw: bool, payload: dict):
        logger.info(f"Using fallback AI Horde to generate image in server {context.guild.id}")
        api_key = (await self.bot.get_shared_api_tokens("ai-horde")).get("api_key") or "0000000000"
        client = StableHordeAPI(self.session, api_key)
        horde_payload = {
            "prompt": payload["prompt"],
            "nsfw": is_allowed_nsfw,
            "censor_nsfw": not context.channel.nsfw,
            "models": ["Anything Diffusion" if await self.config.guild(context.guild).aihorde_anime() else "Deliberate"],
            "params": {
                "sampler_name": "k_euler_a",
                "cfg_scale": payload["cfg_scale"],
                "width": round_to_nearest(payload["width"], 64),
                "height": round_to_nearest(payload["height"], 64),
                "steps": payload["steps"],
            },
        }
        response = await client.txt2img_request(horde_payload)
        if response.get("errors", None):
            logger.error(response)
            return await self.send_response(context, content=":warning: Something went wrong with AI Horde!", ephemeral=True)
        img_uuid = response["id"]
        done = False
        elapsed = 0
        while not done and elapsed < 5 * 60:
            await asyncio.sleep(1)
            elapsed += 1
            generate_check = await client.generate_check(img_uuid)
            done = generate_check["done"] == 1
        generate_status = await client.generate_status(img_uuid)
        if not generate_status["done"]:
            logger.error(f"Failed request to AI Horde in server {context.guild.id}")
            return await self.send_response(context, content=":warning: AI Horde timed out!", ephemeral=True)
        res = generate_status["generations"][0]
        image_url = res["img"]
        async with self.session.get(image_url) as response:
            image_data = await response.read()
        info_string = f"{payload['prompt']}\nAI Horde image. Seed: {res['seed']}, Model: {res['model']}"
        is_nsfw = False
        return image_data, info_string, is_nsfw

    async def _fetch_data(self, guild: discord.Guild, endpoint_suffix):
        res = None
        try:
            endpoint, auth_str, _ = await self._get_endpoint(guild)
            url = endpoint + endpoint_suffix

            async with self.session.get(url, auth=get_auth(auth_str)) as response:
                response.raise_for_status()
                res = await response.json()
        except:
            logger.exception(
                f"Failed getting {endpoint_suffix} from Stable Diffusion endpoint in server {guild.id}")

        return res

    async def _check_endpoint_online(self, guild: discord.Guild):
        endpoint, auth_str, _ = await self._get_endpoint(guild)
        try:
            async with self.session.get(endpoint + "progress", auth=get_auth(auth_str)) as response:
                response.raise_for_status()
                return True
        except:
            return False
