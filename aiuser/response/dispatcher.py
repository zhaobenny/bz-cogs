# response/response_handler.py
import logging

from redbot.core import commands

from aiuser.context.setup import create_messages_thread
from aiuser.response.chat.response import create_chat_response
from aiuser.response.image.generator_factory import get_image_generator
from aiuser.response.image.response import create_image_response
from aiuser.response.is_image_request import is_image_request
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


async def dispatch_response(cog: MixinMeta, ctx: commands.Context, messages_list=None):
    """ Decide which response to send based on the context """
    async with ctx.message.channel.typing():
        if (not messages_list and not ctx.interaction) and await is_image_request(cog, ctx.message):
            if await process_image_response(cog, ctx):
                return

        messages_list = messages_list or await create_messages_thread(cog, ctx)
        return await create_chat_response(cog, ctx, messages_list)


async def process_image_response(cog: MixinMeta, ctx: commands.Context) -> bool:
    """Process and send an image response"""
    await ctx.react_quietly("🧐")

    try:
        generator = await get_image_generator(ctx, cog.config)
        success = await create_image_response(cog, ctx, generator)
        return success
    except Exception:
        logger.warning("Couldn't generate an image response!", exc_info=True)
        return False
    finally:
        await ctx.message.remove_reaction("🧐", ctx.me)