import logging
import re

import discord
from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.common.constants import IMAGE_REQUEST_CHECK_PROMPT
from aiuser.messages_list.messages import create_messages_list
from aiuser.response.chat.openai import OpenAIAPIGenerator
from aiuser.response.chat.response import ChatResponse
from aiuser.response.image.generator_factory import get_image_generator
from aiuser.response.image.response import ImageResponse

logger = logging.getLogger("red.bz_cogs.aiuser")


class ResponseHandler(MixinMeta):
    async def create_response(self, ctx: commands.Context, messages_list=None):
        if (not messages_list and not ctx.interaction) and await self.is_image_request(ctx.message):
            if await self.send_image(ctx):
                return

        messages_list = messages_list or await create_messages_list(self, ctx)

        async with ctx.message.channel.typing():
            chat_generator = OpenAIAPIGenerator(self, ctx, messages_list)
            response = ChatResponse(ctx, self.config, chat_generator)
            await response.send()

    async def send_image(self, ctx: commands.Context):
        await ctx.react_quietly("🧐")
        async with ctx.message.channel.typing():
            generator = await get_image_generator(ctx, self.config)
            response = ImageResponse(self, ctx, generator)
            if await response.send():
                await ctx.message.remove_reaction("🧐", ctx.me)
                return True
        await ctx.message.remove_reaction("🧐", ctx.me)
        return False

    async def is_image_request(self, message: discord.Message) -> bool:
        if not await self.config.guild(message.guild).image_requests():
            return False

        message_content = message.content.lower()
        displayname = (message.guild.me.nick or message.guild.me.display_name).lower()

        trigger_words = await self.config.guild(message.guild).image_requests_trigger_words()
        second_person_words = await self.config.guild(message.guild).image_requests_second_person_trigger_words()

        contains_image_words = any(word in message_content for word in trigger_words)
        contains_second_person = any(word in message_content for word in second_person_words)
        mentioned_me = displayname in message_content or message.guild.me.id in message.raw_mentions
        replied_to_me = message.reference and message.reference.resolved.author.id == message.guild.me.id

        skip_llm_check = await self.config.guild(message.guild).image_requests_reduced_llm_calls()

        return (contains_image_words and contains_second_person and (mentioned_me or replied_to_me) and
                (skip_llm_check or await self.is_image_request_by_llm(message)))

    async def is_image_request_by_llm(self, message: discord.Message) -> bool:
        botname = message.guild.me.nick or message.guild.me.display_name
        text = message.content
        for m in message.mentions:
            text = text.replace(m.mention, m.display_name)
        if message.reference:
            text = f"{await message.reference.resolved.content}\n {text}"
        try:
            response = await self.openai_client.chat.completions.create(
                model=await self.config.guild(message.guild).model(),
                messages=[
                    {"role": "system", "content": IMAGE_REQUEST_CHECK_PROMPT.format(botname=botname)},
                    {"role": "user", "content": text},
                ],
                max_tokens=1,
            )
            return response.choices[0].message.content == "True"
        except Exception:
            logger.exception("Error while checking message for an image request")
            return False
