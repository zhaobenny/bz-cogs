import base64
import io
import logging

import aiohttp
import discord
import openai
from redbot.core import Config, commands

from aiuser.common.constants import SD_GENERATION_PROMPT

logger = logging.getLogger("red.bz_cogs.aiuser")


async def is_image_request(message: discord.Message):
    bool_response = False
    try:
        botname = message.guild.me.nick or message.guild.me.display_name
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                    "content": f"Think step by step. You are {botname}. Is the following a message asking for a picture, image, or picture of yourself? Answer with True/False"},
                {"role": "user", "content": message.content}
            ],
            max_tokens=1,
        )
        bool_response = response["choices"][0]["message"]["content"]
    except:
        logger.error(f"Error while checking message if is a Stable Diffusion request")
    return bool_response == "True"


class StableDiffusionRequest():
    def __init__(self, ctx: commands.Context, config: Config):
        self.ctx = ctx
        self.config = config
        self.message = ctx.message

    async def sent_image(self):
        try:
            caption = await self._create_image_caption()
            await self.message.channel.send(f"Caption: {caption}")  # REMOVE THIS
            if caption is None:
                return False
            image = await self._generate_image(caption)
            await self.message.channel.send(file=discord.File(image, filename="me.png"))
            return True
        except Exception as e:
            logger.error(f"Error while generating image using SD:\n {e}")
            return False

    async def _create_image_caption(self):
        request = self.message.content.replace("yourself", "katsuragi misato").replace("you", "katsuragi misato")

        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SD_GENERATION_PROMPT},
                {"role": "user", "content": request}
            ],
        )
        prompt = response["choices"][0]["message"]["content"].lower()
        if "sorry" in prompt:
            return None
        return prompt

    async def _generate_image(self, caption):
        url = await self.config.guild(self.ctx.guild).SD_endpoint()

        payload = await self.config.guild(self.ctx.guild).SD_parameters() or {
            "prompt": caption,
            "negative_prompt": "worst quality, low quality:1.4",
            "sampler_name": "Euler a",
            "steps": 20,
            "denoising_strength": 0.5,
            "cfg": 5
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url=f'{url}/sdapi/v1/txt2img', json=payload) as response:
                r = await response.json()
        image = (io.BytesIO(base64.b64decode(r['images'][0])))
        return image
