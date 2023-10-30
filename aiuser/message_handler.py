import logging
import re

import discord
import openai
from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.common.constants import (AI_HORDE_MODE, IMAGE_CHECK_REQUEST_PROMPT,
                                     LOCAL_MODE, MAX_MESSAGE_LENGTH,
                                     MIN_MESSAGE_LENGTH, RELATED_IMAGE_WORDS,
                                     SECOND_PERSON_WORDS)
from aiuser.generators.image.request.generic import \
    GenericStableDiffusionGenerator
from aiuser.generators.image.request.response import ImageRequestResponse
from aiuser.generators.image.request.nemusona import NemusonaGenerator
from aiuser.prompts.embed.generic import GenericEmbedPrompt
from aiuser.prompts.embed.youtube import YoutubeLinkPrompt
from aiuser.prompts.image.ai_horde import AIHordeImagePrompt
from aiuser.prompts.sticker_prompt import StickerPrompt
from aiuser.prompts.text_prompt import TextPrompt

logger = logging.getLogger("red.bz_cogs.aiuser")


class MessageHandler(MixinMeta):
    async def handle_message(self, ctx: commands.Context):
        message = ctx.message
        url_pattern = re.compile(r"(https?://\S+)")
        contains_url = url_pattern.search(message.content)
        if message.attachments and await self.config.guild(message.guild).scan_images():
            return await self.handle_image_prompt(ctx)
        elif contains_url and not ctx.interaction:
            return await self.handle_embed_prompt(ctx)
        elif message.stickers:
            return StickerPrompt(self, ctx)
        elif not ctx.interaction and await self.is_image_request(message):
            if await self.handle_image_generation(ctx):
                return None
        if self.is_good_text_message(message) or ctx.interaction:
            return TextPrompt(self, ctx)
        return None

    async def handle_image_prompt(self, ctx: commands.Context):
        message = ctx.message
        async with message.channel.typing():
            if await self.config.guild(message.guild).scan_images_mode() == LOCAL_MODE:
                try:
                    from aiuser.prompts.image.local import LocalImagePrompt
                    return LocalImagePrompt(self, ctx)
                except ImportError:
                    logger.error(
                        f"Unable to load image scanning dependencies, disabling image scanning for this server f{message.guild.name}...")
                    await self.config.guild(message.guild).scan_images.set(False)
                    raise
            elif await self.config.guild(message.guild).scan_images_mode() == AI_HORDE_MODE:
                return AIHordeImagePrompt(self, ctx)

    async def handle_embed_prompt(self, ctx: commands.Context):
        message = ctx.message
        if self.contains_youtube_link(message.content):
            youtube_api = (await self.bot.get_shared_api_tokens("youtube")).get("api_key")
            if youtube_api:
                return YoutubeLinkPrompt(self, ctx)
        return GenericEmbedPrompt(self, ctx)

    async def handle_image_generation(self, ctx: commands.Context):

        sd_endpoint = await self.config.guild(ctx.guild).image_requests_endpoint()

        if sd_endpoint is None:
            logger.error(
                f"Stable Diffusion endpoint not set for {ctx.guild.name}, disabling Stable Diffusion requests for this server...")
            await self.config.guild(ctx.guild).image_requests.set(False)
            return False
        elif sd_endpoint.startswith("https://waifus-api.nemusona.com/"):
            image_generator = NemusonaGenerator(ctx, self.config)
        else:
            image_generator = GenericStableDiffusionGenerator(ctx, self.config)

        async with ctx.message.channel.typing():
            request = ImageRequestResponse(ctx, self.config, image_generator)
            if await request.send():
                return True
        return False

    async def is_image_request(self, message) -> bool:
        if not await self.config.guild(message.guild).image_requests():
            return False

        if await self.config.custom_openai_endpoint() != None:
            await self.config.guild(message.guild).image_requests.set(False)
            logger.warning(
                f"Custom OpenAI endpoint detected, disabling stable-diffusion-webui requests for {message.guild.name}...")
            return False

        message_content = message.content.lower()
        displayname = (message.guild.me.nick or message.guild.me.display_name).lower()

        contains_image_words = any(word in message_content for word in RELATED_IMAGE_WORDS)
        contains_second_person = any(word in message_content for word in SECOND_PERSON_WORDS)
        mentioned_me = displayname in message_content or message.guild.me.id in message.raw_mentions
        replied_to_me = message.reference and message.reference.resolved.author.id == message.guild.me.id

        skip_llm_check = await self.config.guild(message.guild).image_requests_reduced_llm_calls()

        return (contains_image_words and contains_second_person and (mentioned_me or replied_to_me)) and (skip_llm_check or await self.is_image_request_by_llm(message))

    # TODO: find a better place maybe?
    async def is_image_request_by_llm(self, message: discord.Message):
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
                        "content": IMAGE_CHECK_REQUEST_PROMPT.format(botname=botname)},
                    {"role": "user", "content": text}
                ],
                max_tokens=1,
            )
            bool_response = response["choices"][0]["message"]["content"]
        except:
            logger.error(f"Error while checking message if is a Stable Diffusion request")
        return bool_response == "True"

    @staticmethod
    def is_good_text_message(message) -> bool:
        mention_pattern = re.compile(r'^<@!?&?(\d+)>$')

        if not message.content:
            logger.debug(f"Skipping empty message {message.id} in {message.guild.name}")
            return False

        if mention_pattern.match(message.content):
            logger.debug(f"Skipping singular mention message {message.id} in {message.guild.name}")
            return False

        if len(message.content) < MIN_MESSAGE_LENGTH:
            logger.debug(
                f"Skipping short message {message.id} in {message.guild.name}")
            return False

        if len(message.content.split()) > MAX_MESSAGE_LENGTH:
            logger.debug(
                f"Skipping long message {message.id} in {message.guild.name}")
            return False

        return True

    @staticmethod
    def contains_youtube_link(link):
        youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)'
        match = re.search(youtube_regex, link)
        return bool(match)
