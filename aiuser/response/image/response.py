import logging
import re
from typing import Optional

import discord
from openai import AsyncOpenAI
from redbot.core import commands, Config

from aiuser.response.chat.response import create_chat_response
from aiuser.types.abc import MixinMeta
from aiuser.config.constants import IMAGE_REQUEST_REPLY_PROMPT
from aiuser.messages_list.messages import create_messages_list

from aiuser.response.image.providers.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


async def create_image_response(
    cog: MixinMeta, ctx: commands.Context, image_generator: ImageGenerator
) -> bool:
    """Main function to handle image generation and response"""
    image, caption = None, None

    try:
        caption = await create_image_caption(cog.config, ctx.message, cog.openai_client)
        if caption is None:
            return False

        image = await image_generator.generate_image(caption)
        if image is None:
            return False

    except Exception:
        logger.exception("Error while attempting to generate image")
        return False

    saved_caption = await format_saved_caption(cog.config, ctx.message.guild, caption)

    message_list = await create_messages_list(cog, ctx)
    await message_list.add_system(saved_caption, index=len(message_list) + 1)
    await message_list.add_system(IMAGE_REQUEST_REPLY_PROMPT, index=len(message_list) + 1)

    if not (await create_chat_response(cog, ctx, message_list)):
        await clean_error_emojis(ctx.message, ctx)
        await ctx.message.add_reaction("👍")

    image_msg = await ctx.message.channel.send(
        file=discord.File(image, filename=f"{ctx.message.id}.png")
    )

    cog.cached_messages[image_msg.id] = saved_caption
    return True


async def create_image_caption(
    config: Config, message: discord.Message, openai_client: AsyncOpenAI
) -> Optional[str]:
    """Create a caption for the image based on the message content"""
    subject = await config.guild(message.guild).image_requests_subject()
    botname = message.guild.me.nick or message.guild.me.display_name
    request = message.content

    # Replace mentions with display names
    for m in message.mentions:
        request = request.replace(m.mention, m.display_name)

    # Replace trigger words with subject
    trigger_words = await config.guild(message.guild).image_requests_second_person_trigger_words()
    for w in trigger_words:
        pattern = r"\b{}\b".format(re.escape(w))
        request = re.sub(pattern, subject, request, flags=re.IGNORECASE)

    # Replace bot name with subject
    pattern = r"\b{}\b".format(re.escape(botname))
    request = re.sub(pattern, subject, request, flags=re.IGNORECASE)

    # Generate caption using OpenAI
    response = await openai_client.chat.completions.create(
        model=await config.guild(message.guild).model(),
        messages=[
            {
                "role": "system",
                "content": await config.guild(message.guild).image_requests_sd_gen_prompt(),
            },
            {"role": "user", "content": request},
        ],
    )
    prompt = response.choices[0].message.content.lower()

    return None if "sorry" in prompt else prompt


async def format_saved_caption(config: Config, guild: discord.Guild, caption: str) -> str:
    """Format the caption for saving"""
    subject = await config.guild(guild).image_requests_subject()
    pattern = r"\b{}\b".format(re.escape(subject))
    caption = re.sub(pattern, "", caption, flags=re.IGNORECASE)
    caption = re.sub(r"^[\s,]+", "", caption)
    return f"You sent: [Image: A picture of yourself. Keywords describing this picture would be: {caption}]"


async def clean_error_emojis(message: discord.Message, ctx: commands.Context) -> None:
    """Clean up error reaction emojis"""
    emojis = ["💤", "⚠️"]
    for emoji in emojis:
        try:
            await message.remove_reaction(emoji, ctx.me)
        except Exception:
            pass
