import logging
import re

import discord
import openai
from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.common.constants import (
    IMAGE_CHECK_REQUEST_PROMPT,
    MAX_MESSAGE_LENGTH,
    MIN_MESSAGE_LENGTH,
    RELATED_IMAGE_WORDS,
    SECOND_PERSON_WORDS,
)
from aiuser.common.utilities import is_using_openrouter_endpoint
from aiuser.messages_list.messages import create_messages_list
from aiuser.response.chat.openai import OpenAI_Chat_Generator
from aiuser.response.chat.openrouter import OpenRouter_Chat_Generator
from aiuser.response.chat.response import ChatResponse
from aiuser.response.image.generic import GenericStableDiffusionGenerator
from aiuser.response.image.nemusona import NemusonaGenerator
from aiuser.response.image.response import ImageResponse

logger = logging.getLogger("red.bz_cogs.aiuser")


class ResponseHandler(MixinMeta):
    async def send_response(self, ctx: commands.Context):
        if not ctx.interaction and await self.is_image_request(ctx.message):
            if await self.send_image(ctx):
                return
        if self.is_good_text_message(ctx.message) or ctx.interaction:
            await self.send_message(ctx)

    async def send_message(self, ctx: commands.Context):
        message_list = await create_messages_list(self, ctx)
        async with ctx.message.channel.typing():
            await message_list.add_history()
            chat = self.pick_chat_api(ctx, message_list)
            response = ChatResponse(ctx, self.config, chat)
            await response.send()

    def pick_chat_api(self, ctx, message_list):
        if is_using_openrouter_endpoint(self.openai_client):
            chat = OpenRouter_Chat_Generator(self, ctx, message_list)
        else:
            chat = OpenAI_Chat_Generator(self, ctx, message_list)
        return chat

    async def send_image(self, ctx: commands.Context):
        sd_endpoint = await self.config.guild(ctx.guild).image_requests_endpoint()

        if sd_endpoint is None:
            logger.error(
                f"Stable Diffusion endpoint not set for {ctx.guild.name}, disabling Stable Diffusion requests for this server..."
            )
            await self.config.guild(ctx.guild).image_requests.set(False)
            return False
        elif sd_endpoint.startswith("https://waifus-api.nemusona.com/"):
            image_generator = NemusonaGenerator(ctx, self.config)
        else:
            image_generator = GenericStableDiffusionGenerator(ctx, self.config)

        async with ctx.message.channel.typing():
            response = ImageResponse(self, ctx, image_generator)
            if await response.send():
                return True
        return False

    async def is_image_request(self, message) -> bool:
        if not await self.config.guild(message.guild).image_requests():
            return False

        message_content = message.content.lower()
        displayname = (message.guild.me.nick or message.guild.me.display_name).lower()

        contains_image_words = any(
            word in message_content for word in RELATED_IMAGE_WORDS
        )
        contains_second_person = any(
            word in message_content for word in SECOND_PERSON_WORDS
        )
        mentioned_me = (
            displayname in message_content
            or message.guild.me.id in message.raw_mentions
        )
        replied_to_me = (
            message.reference
            and message.reference.resolved.author.id == message.guild.me.id
        )

        skip_llm_check = await self.config.guild(
            message.guild
        ).image_requests_reduced_llm_calls()

        return (
            contains_image_words
            and contains_second_person
            and (mentioned_me or replied_to_me)
        ) and (skip_llm_check or await self.is_image_request_by_llm(message))

    # TODO: find a better place maybe?
    async def is_image_request_by_llm(self, message: discord.Message):
        bool_response = False
        botname = message.guild.me.nick or message.guild.me.display_name
        text = message.content
        for m in message.mentions:
            text = text.replace(m.mention, m.display_name)
        if message.reference:
            text = (
                await message.reference.resolved.content + "\n " + text
            )  # TODO: find a better way to do this
        try:
            response = await self.openai_client.chat.completions.create(
                model=await self.config.guild(message.guild).model(),
                messages=[
                    {
                        "role": "system",
                        "content": IMAGE_CHECK_REQUEST_PROMPT.format(botname=botname),
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=1,
            )
            bool_response = response.choices[0].message.content
        except:
            logger.error(
                f"Error while checking message if is a Stable Diffusion request"
            )
        return bool_response == "True"

    @staticmethod
    def is_good_text_message(message) -> bool:
        mention_pattern = re.compile(r"^<@!?&?(\d+)>$")

        if mention_pattern.match(message.content):
            logger.debug(
                f"Skipping singular mention message {message.id} in {message.guild.name}"
            )
            return False

        if 1 <= len(message.content) < MIN_MESSAGE_LENGTH:
            logger.debug(f"Skipping short message {message.id} in {message.guild.name}")
            return False

        if len(message.content.split()) > MAX_MESSAGE_LENGTH:
            logger.debug(f"Skipping long message {message.id} in {message.guild.name}")
            return False

        return True
