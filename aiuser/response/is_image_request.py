# response/is_image_request.py

import logging

import discord
from redbot.core import Config

from aiuser.config.constants import IMAGE_REQUEST_CHECK_PROMPT
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


async def is_image_request(cog: MixinMeta, message: discord.Message) -> bool:
    """Determine if a message is requesting an image"""
    if message.guild is None:
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
        for a in message.attachments or []:
            if a.filename and any(a.filename.lower().endswith(ext) for ext in image_exts):
                return True
        return False

    if not await cog.config.guild(message.guild).image_requests():
        return False

    guild_config = cog.config.guild(message.guild)

    if not await check_conditions(message, guild_config):
        return False

    if await guild_config.image_requests_reduced_llm_calls():
        return True

    return await _verify(cog, message)


async def check_conditions(message: discord.Message, guild_config: Config) -> bool:
    """Check basic conditions for image request"""
    message_content = message.content.lower()
    displayname = (message.guild.me.nick or message.guild.me.display_name).lower()

    trigger_words = await guild_config.image_requests_trigger_words()
    second_person_words = await guild_config.image_requests_second_person_trigger_words()

    has_image_words = any(word in message_content for word in trigger_words)
    has_second_person = any(word in message_content for word in second_person_words)
    is_mentioned = displayname in message_content or message.guild.me.id in message.raw_mentions
    is_reply = bool(
        message.reference and message.reference.resolved and message.reference.resolved.author.id == message.guild.me.id
    )

    return has_image_words and has_second_person and (is_mentioned or is_reply)


async def _verify(cog: MixinMeta, message: discord.Message) -> bool:
    """Verify image request using LLM"""
    try:
        text = _prepare_message_text(message)
        botname = message.guild.me.nick or message.guild.me.display_name

        response = await cog.openai_client.chat.completions.create(
            model=await cog.config.guild(message.guild).model(),
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


def _prepare_message_text(message: discord.Message) -> str:
    """Prepare message text for LLM verification"""
    text = message.content
    for m in message.mentions:
        text = text.replace(m.mention, m.display_name)

    if message.reference and message.reference.resolved:
        text = f"{message.reference.resolved.content}\n {text}"
    return text 