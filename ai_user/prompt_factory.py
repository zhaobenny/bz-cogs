import logging
import re

import discord
from redbot.core import commands

from ai_user.abc import MixinMeta
from ai_user.common.constants import AI_HORDE_MODE, LOCAL_MODE
from ai_user.common.types import ContextOptions
from ai_user.prompts.embed.generic import GenericEmbedPrompt
from ai_user.prompts.embed.youtube import YoutubeLinkPrompt
from ai_user.prompts.image.ai_horde import AIHordeImagePrompt
from ai_user.prompts.sticker_prompt import StickerPrompt
from ai_user.prompts.text_prompt import TextPrompt

logger = logging.getLogger("red.bz_cogs.ai_user")

class PromptFactory(MixinMeta):
    async def create_prompt_instance(self, ctx: commands.Context):
        message = ctx.message
        start_time = self.override_prompt_start_time.get(ctx.guild.id, None)
        url_pattern = re.compile(r"(https?://\S+)")
        contains_url = url_pattern.search(message.content)
        extra_config = ContextOptions(
            start_time=start_time, ignore_regex=self.ignore_regex[ctx.guild.id], cached_messages=self.cached_messages)
        if message.stickers:
            return StickerPrompt(message, self.config, extra_config)
        elif message.attachments and await self.config.guild(message.guild).scan_images():
            return await self.handle_image_prompt(message, extra_config)
        elif contains_url:
            return await self.handle_embed_prompt(message, extra_config)
        else:
            return TextPrompt(message, self.config, extra_config)

    async def handle_image_prompt(self, message: discord.Message, extra_config):
        async with message.channel.typing():
            if await self.config.guild(message.guild).scan_images_mode() == LOCAL_MODE:
                try:
                    from ai_user.prompts.image.local import LocalImagePrompt
                    return LocalImagePrompt(message, self.config, extra_config)
                except ImportError:
                    logger.error(
                        f"Unable to load image scanning dependencies, disabling image scanning for this server f{message.guild.name}...")
                    await self.config.guild(message.guild).scan_images.set(False)
                    raise
            elif await self.config.guild(message.guild).scan_images_mode() == AI_HORDE_MODE:
                return AIHordeImagePrompt(message, self.config, extra_config, self.bot)

    async def handle_embed_prompt(self, message: discord.Message, extra_config):
        if self.contains_youtube_link(message.content):
            youtube_api = (await self.bot.get_shared_api_tokens("youtube")).get("api_key")
            if youtube_api:
                return YoutubeLinkPrompt(message, self.config, extra_config, youtube_api)
        return GenericEmbedPrompt(message, self.config, extra_config)

    @staticmethod
    def contains_youtube_link(link):
        youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)'
        match = re.search(youtube_regex, link)
        return bool(match)
