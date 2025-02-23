# response/response_handler.py
import logging

from redbot.core import commands

from aiuser.messages_list.messages import create_messages_list
from aiuser.response.chat.openai import OpenAIAPIGenerator
from aiuser.response.chat.response import ChatResponse
from aiuser.response.image.generator_factory import get_image_generator
from aiuser.response.image.response import ImageResponse
from aiuser.response.wants_image import wants_image
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


async def create_response(cog: MixinMeta, ctx: commands.Context, messages_list=None):
    """Create and send either an image or chat response based on the context"""
    if (not messages_list and not ctx.interaction) and await wants_image(cog, ctx.message):
        if await process_image_response(cog, ctx):
            return

    return await process_chat_response(cog, ctx, messages_list)


async def process_chat_response(cog: MixinMeta, ctx: commands.Context, messages_list=None):
    """Process and send a chat response"""
    messages_list = messages_list or await create_messages_list(cog, ctx)

    async with ctx.message.channel.typing():
        chat_generator = OpenAIAPIGenerator(cog, ctx, messages_list)
        response = ChatResponse(ctx, cog.config, chat_generator)
        return await response.send()


async def process_image_response(cog: MixinMeta, ctx: commands.Context) -> bool:
    """Process and send an image response"""
    await ctx.react_quietly("🧐")

    async with ctx.message.channel.typing():
        try:
            generator = await get_image_generator(ctx, cog.config)
            response = ImageResponse(cog, ctx, generator)
            success = await response.send()

            if success:
                await ctx.message.remove_reaction("🧐", ctx.me)
                return True

        finally:
            await ctx.message.remove_reaction("🧐", ctx.me)

    return False
