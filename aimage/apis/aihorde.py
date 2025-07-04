import asyncio
import logging
import random
import sys
from typing import Union

import discord
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.bot import Red

from aimage.abc import MixinMeta
from aimage.apis.base import BaseAPI
from aimage.apis.response import ImageResponse
from aimage.common.params import ImageGenParams

logger = logging.getLogger("red.bz_cogs.aimage")
_ = Translator("AImage", __file__)


AI_HORDE_SAMPLERS = [
    "k_dpm_2",
    "k_dpmpp_2s_a",
    "k_dpm_adaptive",
    "k_dpm_2_a",
    "k_dpm_fast",
    "k_euler_a",
    "k_lms",
    "DDIM",
    "k_euler",
    "k_dpmpp_sde",
    "lcm",
    "dpmsolver",
    "k_heun",
    "k_dpmpp_2m",
]


class AIHorde(BaseAPI):

    def __init__(self, cog: MixinMeta, context: Union[commands.Context, discord.Interaction]):
        super().__init__(cog, context)
        cog.autocomplete_cache[self.guild.id]["samplers"] = AI_HORDE_SAMPLERS
        self.bot: Red = cog.bot

    async def _init(self):
        self.endpoint = await self.config.guild(self.guild).endpoint()
        api_key = (await self.bot.get_shared_api_tokens("aihorde")).get("apikey") or "0000000000"
        self.headers = {"apikey": api_key}

    async def update_autocomplete_cache(self, cache):
        # models only supported
        res = await self.session.get(
            f"{self.endpoint}/v2/status/models?type=image&model_state=known", headers=self.headers
        )
        try:
            res.raise_for_status()
            res = await res.json()
            cache[self.guild.id]["checkpoints"] = [
                model["name"] for model in sorted(res, key=lambda x: x["count"], reverse=True)
            ]
        except Exception:
            pass

    async def generate_image(self, params: ImageGenParams, payload: dict = None):
        if payload:
            payload["params"]["seed"] = str(random.randint(-sys.maxsize - 1, sys.maxsize))
        elif params and params.seed == -1:
            params.seed = random.randint(-sys.maxsize - 1, sys.maxsize)

        # TODO: lora support
        payload = payload or {
            "prompt": params.prompt,
            "params": {
                "sampler_name": params.sampler or await self.config.guild(self.guild).sampler(),
                "cfg_scale": params.cfg or await self.config.guild(self.guild).cfg(),
                "seed": str(params.seed),
                "width": self._round_to_nearest(
                    params.width or await self.config.guild(self.guild).width(), 16
                ),
                "height": self._round_to_nearest(
                    params.height or await self.config.guild(self.guild).height(), 16
                ),
            },
            "nsfw": ((await self.config.guild(self.guild).nsfw())),
            "censor_nsfw": (not (await self.config.guild(self.guild).nsfw())),
            "steps": params.steps or await self.config.guild(self.guild).sampling_steps(),
            "models": [params.checkpoint or await self.config.guild(self.guild).checkpoint()],
        }
        res = await self.session.post(
            f"{self.endpoint}/v2/generate/async", headers=self.headers, json=payload
        )

        if res.status == 400:
            res = await res.json()
            raise ValueError(
                _("{message}: `{errors}`").format(
                    message=res["message"], errors=str(res.get("errors"))
                )
            )

        res.raise_for_status()

        res = await res.json()
        logger.debug(_("AI Horde initial response: {response}").format(response=res))
        uuid = res["id"]
        await self._wait_for_image(uuid)
        res = await self._get_image(uuid)
        image = await (await self.session.get(res["img"])).read()
        return ImageResponse(
            data=image,
            info_string=self._construct_infostring(payload),
            payload=payload,
            extension="webp",
        )

    # TODO: img2img

    async def _wait_for_image(self, uuid: str):
        max_time = 60 * 10
        curr_time = 0
        while not await self._check_image_done(uuid) and curr_time < max_time:
            curr_time += 5
            await asyncio.sleep(5)

    async def _check_image_done(self, uuid: str):
        res = await self.session.get(
            f"{self.endpoint}/v2/generate/check/{uuid}", headers=self.headers
        )
        res.raise_for_status()
        res = await res.json()
        return res["done"] == True

    async def _get_image(self, uuid: str):
        res = await self.session.get(
            f"{self.endpoint}/v2/generate/status/{uuid}", headers=self.headers
        )
        res.raise_for_status()
        res = await res.json()
        return res["generations"][0]

    @staticmethod
    def _construct_infostring(payload: dict):
        params = payload["params"]
        return _(
            "{prompt}\n`AI Horde image` Steps: {steps}, Samplers: {sampler}, CFG Scale: {cfg_scale}, Seed: {seed}, Model: {model}"
        ).format(
            prompt=payload["prompt"],
            steps=payload["steps"],
            sampler=params["sampler_name"],
            cfg_scale=params["cfg_scale"],
            seed=params["seed"],
            model=payload["models"][0],
        )

    @staticmethod
    def _round_to_nearest(x, base):
        return int(base * round(x / base))
