from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Union

from discord import Message
from redbot.core import commands

from aiuser.config.defaults import DEFAULT_AUDIO_UPLOAD_LIMIT
from aiuser.context.converter.audio import (
    create_audio_transcript,
    format_audio,
    is_audio_attachment,
)
from aiuser.context.converter.embeds import (
    format_embed_content,
    format_embed_message_content,
)
from aiuser.context.converter.formatters import (
    format_image_placeholder,
    format_sticker_content,
    format_text_content,
)
from aiuser.context.converter.images import format_image
from aiuser.context.entry import MessageEntry
from aiuser.utils.utilities import contains_youtube_link, is_embed_valid

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser.context")


class MessageConverter:
    def __init__(self, services: "AIUserServices", ctx: commands.Context):
        self.services = services
        self.bot_id: int = services.bot.user.id
        self.init_msg = ctx.message
        self.ctx = ctx

    async def convert(self, message: Message) -> Optional[List[MessageEntry]]:
        """Converts a Discord message to ChatML format message(s)"""
        res: List[MessageEntry] = []
        role = "user" if message.author.id != self.bot_id else "assistant"
        if message.attachments:
            await self.handle_attachment(message, res, role)
        elif message.stickers:
            content = await format_sticker_content(message)
            await self.add_entry(content, res, role)
        elif (
            len(message.embeds) > 0 and is_embed_valid(message)
        ) or contains_youtube_link(message.content):
            await self.handle_embed(message, res, role)
        else:
            content = format_text_content(message)
            await self.add_entry(content, res, role)

        return res or None

    async def handle_attachment(
        self, message: Message, res: List[MessageEntry], role: str
    ):
        attachment = message.attachments[0]
        content_type = attachment.content_type or ""
        is_trigger_attachment = (self.init_msg.id == message.id) or (
            self.init_msg.reference and self.init_msg.reference.message_id == message.id
        )
        can_scan_attachment = is_trigger_attachment and not self.ctx.interaction

        if is_audio_attachment(message):
            should_scan_audio = (
                attachment.size <= DEFAULT_AUDIO_UPLOAD_LIMIT
                and can_scan_attachment
                and message.author.id != self.bot_id
                and await self.services.config.guild(message.guild).scan_audio()
            )
            transcript = (
                await create_audio_transcript(self.services, message)
                if should_scan_audio
                else None
            )
            content = transcript or await format_audio(self.services, message)
        elif not content_type.startswith("image/"):
            content = f'User "{message.author.display_name}" sent: [Attachment: "{message.attachments[0].filename}"]'
        elif attachment.size > await self.services.config.guild(message.guild).max_image_size():
            content = format_image_placeholder(message)
        elif (
            can_scan_attachment and await self.services.config.guild(message.guild).scan_images()
        ):
            content = await format_image(self.services.config, message)
            await self.add_entry(content, res, role)
            return
        else:
            content = format_image_placeholder(message)

        await self.add_entry(content, res, role)
        content = format_text_content(message)
        await self.add_entry(content, res, role)

    async def handle_embed(self, message: Message, res: List[MessageEntry], role: str):
        content = await format_embed_content(self.services.config, self.services.bot, message)
        if not content:
            content = format_text_content(message)
            await self.add_entry(content, res, role)
        else:
            await self.add_entry(content, res, role)
            content = format_embed_message_content(message)
            await self.add_entry(content, res, role)

    async def add_entry(
        self, content: Optional[Union[str, list]], res: List[MessageEntry], role: str
    ):
        if not content:
            return
        res.append(MessageEntry(role, content))
