import base64
import io
import logging
import re

import aiohttp
import discord
import openai
from redbot.core import Config, commands

from aiuser.common.constants import SD_GENERATION_PROMPT, SECOND_PERSON_WORDS

logger = logging.getLogger("red.bz_cogs.aiuser")


async def is_image_request(message: discord.Message):
    bool_response = False
    botname = message.guild.me.nick or message.guild.me.display_name
    text = message.content
    for m in message.mentions:
        text = text.replace(m.mention, m.display_name)
    if message.reference:
        text = await message.reference.resolved.content + "\n " + text  # TODO: find a better way to do this
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                    "content": f"Your task is to classify messages. You are {botname}. Is the following a message asking for a picture, image, or picture that includes yourself or {botname}?  Answer with True/False."},
                {"role": "user", "content": text}
            ],
            max_tokens=500,
        )
        bool_response = response["choices"][0]["message"]["content"]
        return bool_response
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
            if caption is None:
                return False
            image = await self._generate_image(caption)

            await self.message.channel.send(file=discord.File(image, filename=f"{self.message.id}.png"))
            return True
        except Exception as e:
            logger.error(f"Error while generating image using SD:\n {e}")
            return False

    async def _create_image_caption(self):
        config = self.config.guild(self.ctx.guild)
        subject = await config.SD_subject()

        botname = self.message.guild.me.nick or self.message.guild.me.display_name
        request = self.message.content

        for m in self.message.mentions:
            request = request.replace(m.mention, m.display_name)

        for w in SECOND_PERSON_WORDS:
            pattern = r'\b{}\b'.format(re.escape(w))  # \b denotes a word boundary
            request = re.sub(pattern, subject, request, flags=re.IGNORECASE)

        pattern = r'\b{}\b'.format(re.escape(botname))
        request = re.sub(pattern, subject, request, flags=re.IGNORECASE)

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
            "negative_prompt": "worst quality, low quality",
            "sampler_name": "Euler a",
            "steps": 20,
        }

        payload["prompt"] = await self.config.guild(self.ctx.guild).SD_preprompt() + " " + caption

        async with aiohttp.ClientSession() as session:
            async with session.post(url=f'{url}/sdapi/v1/txt2img', json=payload) as response:
                r = await response.json()
        image = (io.BytesIO(base64.b64decode(r['images'][0])))
        return image
