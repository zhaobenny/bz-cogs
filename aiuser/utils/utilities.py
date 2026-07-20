import asyncio
import functools
import logging
import random
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Coroutine, TypeVar

import discord
import tiktoken
from discord import Message
from redbot.core import commands

from aiuser.config.constants import (
    FALLBACK_TOKENIZER,
    YOUTUBE_URL_PATTERN,
)

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")

PROMPT_SCOPE_VARIABLES = ("serverprompt", "channelprompt", "roleprompt")


def get_tokenizer_encoding(model: str):
    try:
        return tiktoken.encoding_for_model(model), model, False
    except KeyError:
        model_name = str(model or "")
        base_name = model_name.rsplit("/", 1)[-1]
        if base_name.startswith(("gpt-5.", "gpt-4.1.", "gpt-4o.")):
            try:
                return tiktoken.get_encoding("o200k_base"), "o200k_base", True
            except ValueError:
                logger.debug(
                    "tiktoken does not provide o200k_base; falling back to %s",
                    FALLBACK_TOKENIZER,
                )
        return tiktoken.get_encoding(FALLBACK_TOKENIZER), FALLBACK_TOKENIZER, True


_T = TypeVar("_T")


def to_thread(timeout: float = 300):
    def decorator(func: Callable[..., _T]) -> Callable[..., Coroutine[Any, Any, _T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> _T:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, func, *args, **kwargs), timeout
            )
            return result

        return wrapper

    return decorator


async def _get_prompt_scope_variables(
    ctx: commands.Context,
    text: str,
    format_values: dict,
    services: "AIUserServices",
):
    names_to_fetch = {name for name in PROMPT_SCOPE_VARIABLES if f"{{{name}}}" in text}
    if not names_to_fetch:
        return {}

    prompt_values = {}
    while names_to_fetch:
        name = names_to_fetch.pop()
        if name == "serverprompt":
            value = await services.resolver.resolve_prompt(guild=ctx.guild) or ""
        elif name == "channelprompt":
            value = (
                await services.config.channel(ctx.channel).custom_text_prompt() or ""
            )
        else:  # roleprompt
            value = ""
            if isinstance(ctx.message.author, discord.Member):
                value = (
                    await services.resolver.get_role_override(
                        ctx.message.author, "custom_text_prompt"
                    )
                    or ""
                )
        prompt_values[name] = value
        names_to_fetch |= {
            name
            for name in PROMPT_SCOPE_VARIABLES
            if f"{{{name}}}" in value and name not in prompt_values
        }

    # Expand broadest scope first so a channel/role prompt can embed
    # {serverprompt}; the reverse direction leaves the token as-is.
    known_tokens = tuple(
        f"{{{key}}}" for key in (*format_values, *PROMPT_SCOPE_VARIABLES)
    )
    for name in PROMPT_SCOPE_VARIABLES:
        value = prompt_values.get(name)
        if not value or not any(token in value for token in known_tokens):
            continue
        other_values = {**format_values, **prompt_values}
        other_values.pop(name)
        try:
            prompt_values[name] = value.format(**other_values)
        except (KeyError, ValueError, IndexError):
            logger.exception("Invalid format string in scoped prompt")
    return prompt_values


async def format_variables(
    ctx: commands.Context, text: str, services: "AIUserServices"
):
    """
    Insert supported variables into string if they are present
    """
    botname = ctx.message.guild.me.nick or ctx.bot.user.display_name
    owners = [
        ctx.bot.get_user(owner_id) or await ctx.bot.fetch_user(owner_id)
        for owner_id in sorted(ctx.bot.owner_ids)
    ]
    botowner = ", ".join(owner.name for owner in owners)
    authorname = ctx.message.author.display_name
    # Webhook messages have User objects instead of Member objects
    if isinstance(ctx.message.author, discord.Member):
        authortoprole = ctx.message.author.top_role.name
    else:
        authortoprole = "Webhook"  # Default for webhook messages
    authormention = ctx.message.author.mention

    servername = ctx.guild.name
    channelname = ctx.message.channel.name
    currentdate = datetime.today().strftime("%Y/%m/%d")
    currentweekday = datetime.today().strftime("%A")
    currenttime = datetime.today().strftime("%H:%M")

    randomnumber = random.randint(0, 100)

    if isinstance(ctx.message.channel, discord.Thread):
        channeltopic = getattr(ctx.message.channel.parent, "topic", "No topic found")
    else:
        channeltopic = getattr(ctx.message.channel, "topic", "No topic found")

    serveremojis = [str(e) for e in ctx.message.guild.emojis]
    random.shuffle(serveremojis)
    serveremojis = " ".join(serveremojis)
    format_values = {
        "botname": botname,
        "botowner": botowner,
        "authorname": authorname,
        "authortoprole": authortoprole,
        "authormention": authormention,
        "servername": servername,
        "serveremojis": serveremojis,
        "channelname": channelname,
        "channeltopic": channeltopic,
        "currentdate": currentdate,
        "currentweekday": currentweekday,
        "currenttime": currenttime,
        "randomnumber": randomnumber,
    }
    format_values.update(
        await _get_prompt_scope_variables(ctx, text, format_values, services)
    )

    try:
        known_tokens = tuple(f"{{{key}}}" for key in format_values)
        if not any(token in text for token in known_tokens):
            return text
        res = text.format(**format_values)
        return res
    except (KeyError, ValueError, IndexError):
        logger.exception("Invalid format string in message", exc_info=True)
        return text


def mention_to_text(message: Message) -> str:
    """
    Converts mentions to text
    """
    content = message.content
    mentions = message.mentions + message.role_mentions + message.channel_mentions

    if not mentions:
        return content

    for mentioned in mentions:
        if mentioned in message.channel_mentions:
            content = content.replace(mentioned.mention, f"#{mentioned.name}")
        elif mentioned in message.role_mentions:
            content = content.replace(mentioned.mention, f"@{mentioned.name}")
        else:
            content = content.replace(mentioned.mention, f"@{mentioned.display_name}")

    return content


def is_embed_valid(message: Message):
    if (
        (len(message.embeds) == 0)
        or (not message.embeds[0].title)
        or (not message.embeds[0].description)
    ):
        return False
    return True


async def wait_for_embed(ctx: commands.Context) -> commands.Context:
    start_time = asyncio.get_event_loop().time()
    while not is_embed_valid(ctx.message):
        ctx.message = await ctx.channel.fetch_message(ctx.message.id)
        if asyncio.get_event_loop().time() - start_time >= 3:
            break
        await asyncio.sleep(1)
    return ctx


def contains_youtube_link(content):
    match = YOUTUBE_URL_PATTERN.search(content)
    return bool(match)


async def encode_text_to_tokens(text: str, model: str = FALLBACK_TOKENIZER) -> int:
    encoding, _, _ = get_tokenizer_encoding(model)
    return await asyncio.to_thread(
        lambda: len(encoding.encode(text, disallowed_special=()))
    )
