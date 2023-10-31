import logging
import re

import discord
import openai
from redbot.core import Config, commands

from aiuser.common.constants import (IMAGE_GENERATION_PROMPT,
                                     SECOND_PERSON_WORDS)
from aiuser.response.image.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class ImageResponse():
    def __init__(self, ctx: commands.Context, config: Config, image_generator: ImageGenerator):
        self.ctx = ctx
        self.config = config
        self.message = ctx.message
        self.image_generator = image_generator

    async def send(self):
        try:
            caption = await self._create_image_caption()
            if caption is None:
                return False

            image = await self.image_generator.generate_image(caption)
            if image is None:
                return False

            await self.message.channel.send(file=discord.File(image, filename=f"{self.message.id}.png"))
            return True
        except Exception as e:
            logger.error(f"Error while generating image", exc_info=True)
            return False

    async def _create_image_caption(self):
        subject = await self.config.guild(self.ctx.guild).image_requests_subject()

        botname = self.message.guild.me.nick or self.message.guild.me.display_name
        request = self.message.content

        for m in self.message.mentions:
            request = request.replace(m.mention, m.display_name)

        for w in SECOND_PERSON_WORDS:
            pattern = r'\b{}\b'.format(re.escape(w))
            request = re.sub(pattern, subject, request, flags=re.IGNORECASE)

        pattern = r'\b{}\b'.format(re.escape(botname))
        request = re.sub(pattern, subject, request, flags=re.IGNORECASE)

        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": IMAGE_GENERATION_PROMPT},
                {"role": "user", "content": request}
            ],
        )
        prompt = response["choices"][0]["message"]["content"].lower()
        if "sorry" in prompt:
            return None
        return prompt
