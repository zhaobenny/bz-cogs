import logging
import re

import discord
from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.common.constants import IMAGE_REQUEST_SD_GEN_PROMPT

from aiuser.messages_list.messages import create_messages_list
from aiuser.response.chat.openai import OpenAI_API_Generator
from aiuser.response.chat.response import ChatResponse
from aiuser.response.image.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class ImageResponse():
    def __init__(self, cog: MixinMeta, ctx: commands.Context, image_generator: ImageGenerator):
        self.ctx = ctx
        self.config = cog.config
        self.cog = cog
        self.message = ctx.message
        self.image_generator = image_generator

    async def send(self):
        image, caption = None, None

        try:
            caption = await self._create_image_caption()
            if caption is None:
                return False

            image = await self.image_generator.generate_image(caption)
            if image is None:
                return False

        except:
            logger.error(f"Error while generating image", exc_info=True)
            return False

        response = None
        saved_caption = await self._format_saved_caption(caption)
        if (await self.config.guild(self.message.guild).image_requests_reduced_llm_calls()):
            await self.message.add_reaction("👍")
        else:
            message_list = await create_messages_list(self.cog, self.ctx)
            await message_list.add_history()
            await message_list.add_system(
                saved_caption, index=len(message_list) + 1)
            await message_list.add_system(
                "You sent the above image. Respond accordingly", index=len(message_list) + 1)
            chat = OpenAI_API_Generator(self.cog, self.ctx, message_list)
            response = ChatResponse(self.ctx, self.config, chat)

        if response is not None:
            await response.send()
        image_msg = await self.message.channel.send(file=discord.File(image, filename=f"{self.message.id}.png"))

        self.cog.cached_messages[image_msg.id] = saved_caption
        return True

    async def _create_image_caption(self):
        subject = await self.config.guild(self.message.guild).image_requests_subject()

        botname = self.message.guild.me.nick or self.message.guild.me.display_name
        request = self.message.content

        for m in self.message.mentions:
            request = request.replace(m.mention, m.display_name)

        for w in (await self.config.guild(self.ctx.guild).image_requests_second_person_trigger_words()):
            pattern = r'\b{}\b'.format(re.escape(w))
            request = re.sub(pattern, subject, request, flags=re.IGNORECASE)

        pattern = r'\b{}\b'.format(re.escape(botname))
        request = re.sub(pattern, subject, request, flags=re.IGNORECASE)

        response = await self.cog.openai_client.chat.completions.create(
            model=await self.config.guild(self.message.guild).model(),
            messages=[
                {"role": "system", "content": IMAGE_REQUEST_SD_GEN_PROMPT},
                {"role": "user", "content": request}
            ],
        )
        prompt = response.choices[0].message.content.lower()
        if "sorry" in prompt:
            return None
        return prompt

    async def _format_saved_caption(self, caption):
        subject = await self.config.guild(self.message.guild).image_requests_subject()

        pattern = r'\b{}\b'.format(re.escape(subject))
        caption = re.sub(pattern, "", caption, flags=re.IGNORECASE)
        caption = re.sub(r'^[\s,]+', '', caption)
        return f"You sent: [Image: A picture of yourself. Keywords describing this picture would be: {caption}]"
