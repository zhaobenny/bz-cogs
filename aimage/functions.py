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
from aimage.constants import ADETAILER_ARGS, VIEW_TIMEOUT
from aimage.stablehordeapi import StableHordeAPI
from aimage.views import ImageActions

logger = logging.getLogger("red.bz_cogs.aimage")


def round_to_nearest(x, base):
    return int(base * round(x/base))


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
                             width: int = None,
                             height: int = None,
                             checkpoint: str = None,
                             payload: dict = None):

        if isinstance(context, discord.Interaction):
            await context.response.defer(thinking=True)
        else:
            await context.message.add_reaction("⏳")

        guild = context.guild

        endpoint, auth_str, nsfw = await self._get_endpoint(guild)
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
            "override_settings": {
                "sd_model_checkpoint": checkpoint or await self.config.guild(guild).checkpoint(),
            },
            "width": width or await self.config.guild(guild).width(),
            "height": height or await self.config.guild(guild).height(),
        }

        if await self.config.guild(guild).adetailer():
            payload["alwayson_scripts"] = ADETAILER_ARGS

        if not nsfw:
            payload["script_name"] = "CensorScript"
            payload["script_args"] = [True, True]

        try:
            image_data, info_string, is_nsfw = await self._post_sd_endpoint(endpoint, payload, auth_str)
            image_extension = "png"
        except:
            if await self.config.aihorde():
                image_data, info_string, is_nsfw = await self._request_aihorde(context, nsfw, payload)
                image_extension = ".webp"
            else:
                logger.exception(f"Failed request to Stable Diffusion endpoint in server {guild.id}")
                return await self.sent_response(context, content=":warning: Something went wrong!", ephemeral=True)

        user = context.user if isinstance(
            context, discord.Interaction) else context.author
        if is_nsfw:
            return await self.sent_response(context, content=f"🔞 {user.mention} generated a possible NSFW image with prompt: `{prompt}`", allowed_mentions=discord.AllowedMentions.none())

        msg = await self.sent_response(context, file=discord.File(io.BytesIO(image_data), filename=f"image.{image_extension}"), view=ImageActions(cog=self, image_info=info_string, payload=payload, author=user))
        asyncio.create_task(self.delete_button_after(msg))

    async def sent_response(self, context: Union[commands.Context, discord.Interaction], **kwargs):
        if isinstance(context, discord.Interaction):
            return await context.followup.send(**kwargs)
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
        return (endpoint, auth, nsfw)

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
    async def _post_sd_endpoint(self, endpoint, payload, auth_str):
        url = endpoint + "txt2img"

        async with self.session.post(url=url, json=payload, auth=self.get_auth(auth_str)) as response:
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
            return await self.sent_response(context, content=":warning: Something went wrong!", ephemeral=True)
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
            return await self.sent_response(context, content=":warning: Something went wrong!", ephemeral=True)
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

            async with self.session.get(url, auth=self.get_auth(auth_str)) as response:
                response.raise_for_status()
                res = await response.json()
        except:
            logger.exception(
                f"Failed getting {endpoint_suffix} from Stable Diffusion endpoint in server {guild.id}")

        return res

    async def _check_endpoint_online(self, guild: discord.Guild):
        endpoint, auth_str, _ = await self._get_endpoint(guild)
        try:
            async with self.session.get(endpoint + "progress", auth=self.get_auth(auth_str)) as response:
                response.raise_for_status()
                return True
        except:
            return False

    def get_auth(self, auth_str: str):
        """ Format auth string to aiohttp.BasicAuth """
        auth = None
        if auth_str:
            username, password = auth_str.split(':')
            auth = aiohttp.BasicAuth(username, password)
        return auth

    # https://github.com/hollowstrawberry/crab-cogs/blob/b1f28057ae9760dbc1d51dadb290bdeb141642bf/novelai/novelai.py#L200C1-L200C74
    @staticmethod
    async def delete_button_after(msg: discord.Message):
        await asyncio.sleep(VIEW_TIMEOUT)
        try:
            await msg.edit(view=None)
        except:
            return
