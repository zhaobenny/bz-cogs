import asyncio
import logging
import random
import re
from datetime import datetime, timezone

from discord import AllowedMentions
from redbot.core import Config, commands

from aiuser.messages_list.messages import MessagesList
from aiuser.response.chat.llm_pipeline import LLMPipeline
from aiuser.types.abc import MixinMeta
from aiuser.utils.constants import REGEX_RUN_TIMEOUT
from aiuser.utils.utilities import to_thread

logger = logging.getLogger("red.bz_cogs.aiuser")

async def create_chat_response(cog: MixinMeta, ctx: commands.Context, messsages_list: MessagesList):

    pipeline = LLMPipeline(cog, ctx, messages=messsages_list)
    response = await pipeline.create_completion()
    
    if not response:
        return False
        
    response = await remove_patterns_from_response(ctx, cog.config, response)
    
    if not response:
        return False

    return await send_response(ctx, response, messsages_list.can_reply)

async def remove_patterns_from_response(ctx: commands.Context, config: Config, response: str) -> str:
    """Remove specified patterns from the response text"""
    
    @to_thread(timeout=REGEX_RUN_TIMEOUT)
    def substitute(pattern: re.Pattern, text: str) -> str:
        return pattern.sub('', text).strip(' \n')

    @to_thread(timeout=REGEX_RUN_TIMEOUT)
    def compile_pattern(pattern: str) -> re.Pattern:
        return re.compile(pattern)

    # Get and process patterns
    patterns = await config.guild(ctx.guild).removelist_regexes()
    botname = ctx.message.guild.me.nick or ctx.bot.user.display_name
    patterns = [pattern.replace(r'{botname}', botname) for pattern in patterns]

    # Process author patterns
    authors = {m.author.display_name async for m in ctx.channel.history(limit=10) 
              if m.author != ctx.guild.me}

    authorname_patterns = [p for p in patterns if r'{authorname}' in p]
    regular_patterns = [p for p in patterns if r'{authorname}' not in p]
    
    # Expand author patterns
    for pattern in authorname_patterns:
        for author in authors:
            regular_patterns.append(pattern.replace(r'{authorname}', author))

    # Compile patterns
    compiled_patterns = []
    for pattern in regular_patterns:
        try:
            compiled = await compile_pattern(pattern)
            compiled_patterns.append(compiled)
        except asyncio.TimeoutError:
            logger.warning(
                f"Timed out after {REGEX_RUN_TIMEOUT} seconds while compiling regex pattern \"{pattern}\", continuing...")
        except Exception:
            logger.warning(
                f"Failed to compile regex pattern \"{pattern}\" for response \"{response}\"", 
                exc_info=True)

    # Apply patterns
    processed_response = response.strip(' \n')
    for pattern in compiled_patterns:
        try:
            processed_response = await substitute(pattern, processed_response)
        except asyncio.TimeoutError:
            logger.warning(
                f"Timed out after {REGEX_RUN_TIMEOUT} seconds while applying regex pattern "
                f"\"{pattern.pattern}\" in response \"{response}\". Check pattern for catastrophic backtracking.")

    return processed_response

async def should_reply(ctx: commands.Context) -> bool:
    """Determine if the bot should reply to a message"""
    if ctx.interaction:
        return False

    try:
        await ctx.fetch_message(ctx.message.id)
    except Exception:
        return False

    time_diff = datetime.now(timezone.utc) - ctx.message.created_at

    if time_diff.total_seconds() > 8 or random.random() < 0.25:
        return True

    try:
        async for last_message in ctx.message.channel.history(limit=1):
            if last_message.author == ctx.message.guild.me:
                return True
    except Exception:
        pass

    return False

async def send_response(ctx: commands.Context, response: str, can_reply: bool) -> bool:
    """Send the response in appropriate chunks"""
    allowed_mentions = AllowedMentions(
        everyone=False, 
        roles=False, 
        users=[ctx.message.author]
    )

    if len(response) >= 2000:
        chunks = [response[i:i + 2000] for i in range(0, len(response), 2000)]
        for chunk in chunks:
            await ctx.send(chunk, allowed_mentions=allowed_mentions)
    elif can_reply and await should_reply(ctx):
        await ctx.message.reply(response, mention_author=False, allowed_mentions=allowed_mentions)
    elif ctx.interaction:
        await ctx.interaction.followup.send(response, allowed_mentions=allowed_mentions)
    else:
        await ctx.send(response, allowed_mentions=allowed_mentions)
    
    return True