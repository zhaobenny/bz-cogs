# response/response_handler.py
import logging

from redbot.core import commands

from aiuser.context.setup import create_messages_thread
from aiuser.response.chat.response import create_chat_response
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


async def dispatch_response(cog: MixinMeta, ctx: commands.Context, messages_list=None):
    """ Decide which response to send based on the context """
    async with ctx.message.channel.typing():
        messages_list = messages_list or await create_messages_thread(cog, ctx)
        return await create_chat_response(cog, ctx, messages_list)

