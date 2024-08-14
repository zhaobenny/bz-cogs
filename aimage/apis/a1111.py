import base64
import json
import logging
from enum import Enum

from tenacity import retry, stop_after_attempt, wait_random

from aimage.apis.base import BaseAPI
from aimage.apis.response import ImageResponse
from aimage.common.constants import ADETAILER_ARGS, TILED_VAE_ARGS
from aimage.common.helpers import get_auth
from aimage.common.params import ImageGenParams

logger = logging.getLogger("red.bz_cogs.aimage")


class ImageGenerationType(Enum):
    TXT2IMG = "txt2img"
    IMG2IMG = "img2img"


class A1111(BaseAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _init(self):
        self.endpoint = await self.config.guild(self.guild).endpoint()
        self.auth = get_auth(await self.config.guild(self.guild).auth())

    async def _generate_payload(self, params: ImageGenParams, init_image: bytes = None) -> dict:
        payload = {
            "prompt": f"{params.prompt} {params.lora}",
            "negative_prompt": params.negative_prompt or await self.config.guild(self.guild).negative_prompt(),
            "styles": params.style.split(", ") if params.style else [],
            "cfg_scale": params.cfg or await self.config.guild(self.guild).cfg(),
            "steps": params.steps or await self.config.guild(self.guild).sampling_steps(),
            "seed": params.seed,
            "subseed": params.subseed,
            "subseed_strength": params.subseed_strength,
            "sampler_name": params.sampler or await self.config.guild(self.guild).sampler(),
            "scheduler": params.scheduler or "Automatic",
            "override_settings": {
                "sd_model_checkpoint": params.checkpoint or await self.config.guild(self.guild).checkpoint(),
                "sd_vae": params.vae or await self.config.guild(self.guild).vae()
            },
            "width": params.width or await self.config.guild(self.guild).width(),
            "height": params.height or await self.config.guild(self.guild).height(),
            "alwayson_scripts": {}
        }

        if init_image:
            payload.update({
                "init_images": [base64.b64encode(init_image).decode("utf8")],
                "denoising_strength": params.denoising
            })

        if await self.config.guild(self.guild).adetailer():
            payload["alwayson_scripts"].update(ADETAILER_ARGS)

        if await self.config.guild(self.guild).tiledvae():
            payload["alwayson_scripts"].update(TILED_VAE_ARGS)

        if not (await self.config.guild(self.guild).nsfw()):
            payload["script_name"] = "CensorScript"
            payload["script_args"] = [True, True]

        return payload

    async def generate_image(self, params: ImageGenParams, payload: dict = None):
        payload = payload or await self._generate_payload(params)
        return await self._post_image_gen(payload, ImageGenerationType.TXT2IMG)

    async def generate_img2img(self, params: ImageGenParams, payload: dict = None):
        init_image = params.init_image if params.init_image else None
        payload = payload or await self._generate_payload(params, init_image)
        return await self._post_image_gen(payload, ImageGenerationType.IMG2IMG)

    @retry(wait=wait_random(min=3, max=5), stop=stop_after_attempt(3), reraise=True)
    async def _post_image_gen(self, payload, generation_type: ImageGenerationType):
        url = self.endpoint + generation_type.value
        async with self.session.post(url=url, json=payload, auth=self.auth, raise_for_status=True) as response:
            r = await response.json()
            data = base64.b64decode(r["images"][0])

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

        return ImageResponse(data=data, info_string=info_string, is_nsfw=is_nsfw, payload=payload)
