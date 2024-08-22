

import asyncio
import json
import random

from aimage.apis.base import BaseAPI
from aimage.apis.response import ImageResponse
from aimage.common.params import ImageGenParams


class AIHorde(BaseAPI):
    # TODO: make this more fleshed out

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _init(self):
        self.endpoint = await self.config.guild(self.guild).endpoint()
        self.headers = {'apikey': "0000000000"}

    async def generate_image(self, params: ImageGenParams, payload: dict = None):
        if payload:
            payload["params"]["seed"] = str(random.randint(0, 1000000))
        elif params and params.seed == -1:
            params.seed = random.randint(0, 1000000)

        payload = payload or {
            "prompt": params.prompt,
            "params": {
                "sampler_name": params.sampler or await self.config.guild(self.guild).sampler(),
                "cfg_scale": params.cfg or await self.config.guild(self.guild).cfg(),
                "seed":  str(params.seed),
                "width": params.width or await self.config.guild(self.guild).width(),
                "height": params.height or await self.config.guild(self.guild).height(),
            },
            "nsfw": ((await self.config.guild(self.guild).nsfw())),
            "steps": params.steps or await self.config.guild(self.guild).sampling_steps(),
            "models": ["Anything Diffusion"],
        }
        res = await self.session.post(f"{self.endpoint}/v2/generate/async", headers=self.headers, json=payload)

        if res.status == 400:
            res = await res.json()
            raise ValueError(res["message"])

        res.raise_for_status()

        res = await res.json()
        uuid = res["id"]
        await self._wait_for_image(uuid)
        res = await self._get_image(uuid)
        image = await (await self.session.get(res['img'])).read()
        return ImageResponse(data=image, info_string=f"{payload['prompt']}\nAI Horde image. Seed: {payload['params'].get('seed')}, Model: {payload['models'][0]}", payload=payload, extension="webp")

    async def _wait_for_image(self, uuid: str):
        max_time = 60 * 10
        curr_time = 0
        while not await self._check_image_done(uuid) and curr_time < max_time:
            curr_time += 5
            await asyncio.sleep(5)

    async def _check_image_done(self, uuid: str):
        res = await self.session.get(f"{self.endpoint}/v2/generate/check/{uuid}", headers=self.headers)
        res.raise_for_status()
        res = await res.json()
        return res["done"] == True

    async def _get_image(self, uuid: str):
        res = await self.session.get(f"{self.endpoint}/v2/generate/status/{uuid}", headers=self.headers)
        res.raise_for_status()
        res = await res.json()
        return res["generations"][0]
