import logging
import re

from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.generators.image.stable_diffusion import StableDiffusionRequest, is_image_request
from aiuser.common.constants import (AI_HORDE_MODE, LOCAL_MODE,
                                     MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH,
                                     RELATED_IMAGE_WORDS, SECOND_PERSON_WORDS)
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
        elif await self.is_image_gen_request(message):
            if await self.handle_image_gen(ctx):
                return None
        return None  # REMOVE THIS
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


    async def handle_image_gen(self, ctx: commands.Context):
        request = StableDiffusionRequest(ctx, self.config)
        if await request.sent_image():
            return True
        return False
    async def is_image_gen_request(self, message) -> bool:
        if not await self.config.guild(message.guild).SD_requests():
            return False

        if await self.config.custom_openai_endpoint() != None:
            await self.config.guild(message.guild).SD_requests.set(False)
            logger.warning(
                f"Custom OpenAI endpoint detected, disabling stable-diffusion-webui requests for {message.guild.name}...")
            return False

        message_content = message.content.lower()
        displayname = (message.guild.me.nick or message.guild.me.display_name).lower()

        contains_image_words = any(word in message_content for word in RELATED_IMAGE_WORDS)
        contains_second_person = any(word in message_content for word in SECOND_PERSON_WORDS)
        mentioned_me = displayname in message_content or message.guild.me.id in message.raw_mentions
        replied_to_me = message.reference and message.reference.resolved.author.id == message.guild.me.id

        return (contains_image_words and contains_second_person and (mentioned_me or replied_to_me)) and await is_image_request(message)

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
