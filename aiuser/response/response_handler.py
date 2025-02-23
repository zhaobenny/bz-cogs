import logging

import discord
from redbot.core import commands

from aiuser.types.abc import MixinMeta
from aiuser.utils.constants import IMAGE_REQUEST_CHECK_PROMPT
from aiuser.messages_list.messages import create_messages_list
from aiuser.response.chat.openai import OpenAIAPIGenerator
from aiuser.response.chat.response import ChatResponse
from aiuser.response.image.generator_factory import get_image_generator
from aiuser.response.image.response import ImageResponse

logger = logging.getLogger("red.bz_cogs.aiuser")

async def create_response(cog: MixinMeta, ctx: commands.Context, messages_list=None):
    """Create and send either an image or chat response based on the context"""
    # Check if this is an image request
    if (not messages_list and not ctx.interaction) and await is_image_request(cog, ctx.message):
        if await send_image_response(cog, ctx):
            return

    # Otherwise generate a chat response
    messages_list = messages_list or await create_messages_list(cog, ctx)
    
    async with ctx.message.channel.typing():
        chat_generator = OpenAIAPIGenerator(cog, ctx, messages_list)
        response = ChatResponse(ctx, cog.config, chat_generator)
        await response.send()

async def send_image_response(cog: MixinMeta, ctx: commands.Context) -> bool:
    """Attempt to send an image response"""
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

async def is_image_request(cog: MixinMeta, message: discord.Message) -> bool:
    """Determine if a message is requesting an image"""
    # Early return if image requests are disabled
    if not await cog.config.guild(message.guild).image_requests():
        return False

    # Get relevant configuration and message details
    guild_config = cog.config.guild(message.guild)
    message_content = message.content.lower()
    displayname = (message.guild.me.nick or message.guild.me.display_name).lower()

    # Check various conditions
    trigger_words = await guild_config.image_requests_trigger_words()
    second_person_words = await guild_config.image_requests_second_person_trigger_words()
    
    conditions = {
        "contains_image_words": any(word in message_content for word in trigger_words),
        "contains_second_person": any(word in message_content for word in second_person_words),
        "mentioned_me": displayname in message_content or message.guild.me.id in message.raw_mentions,
        "replied_to_me": bool(message.reference and message.reference.resolved and 
                            message.reference.resolved.author.id == message.guild.me.id)
    }

    # All basic conditions must be met
    if not (conditions["contains_image_words"] and 
            conditions["contains_second_person"] and 
            (conditions["mentioned_me"] or conditions["replied_to_me"])):
        return False

    # Check if we can skip LLM verification
    skip_llm_check = await guild_config.image_requests_reduced_llm_calls()
    if skip_llm_check:
        return True

    return await verify_image_request_with_llm(cog, message)

async def verify_image_request_with_llm(cog: MixinMeta, message: discord.Message) -> bool:
    """Use LLM to verify if message is requesting an image"""
    botname = message.guild.me.nick or message.guild.me.display_name
    
    # Prepare message text
    text = message.content
    for m in message.mentions:
        text = text.replace(m.mention, m.display_name)
    
    if message.reference:
        text = f"{await message.reference.resolved.content}\n {text}"

    try:
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