import logging
from textwrap import shorten

import discord
from emoji import EMOJI_DATA

from aiuser.context.converter.formatters import mention_to_text

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


def message_preview(content: str) -> str:
    preview = " ".join(content.split())
    return shorten(preview, width=48, placeholder="...") or "[no text content]"


def parse_custom_emoji(bot, value: str):
    parsed = discord.PartialEmoji.from_str(value)
    if not parsed.id:
        return None
    return discord.utils.get(bot.emojis, name=parsed.name, id=parsed.id)


async def add_reaction(request, emoji: str):
    emoji = str(emoji).strip()

    if request.ctx.interaction:
        return "Cannot add reaction during slash command interactions."

    if emoji in EMOJI_DATA:
        reaction = emoji
    else:
        reaction = parse_custom_emoji(request.bot, emoji)

    if reaction is None:
        return (
            "Invalid emoji: provide exactly one Unicode emoji or raw custom "
            "Discord emoji usable by this bot."
        )

    permissions = request.ctx.channel.permissions_for(request.ctx.me)
    if not permissions.add_reactions:
        return "Missing Add Reactions permission."

    try:
        await request.ctx.message.add_reaction(reaction)
    except discord.Forbidden:
        return "Missing Add Reactions permission."
    except discord.NotFound:
        return "Could not add reaction because the message or emoji was not found."
    except discord.HTTPException:
        logger.exception("Failed to add reaction %r", emoji)
        return "Could not add that reaction."

    return (
        f"Added reaction {emoji} to the message: "
        f'"{message_preview(mention_to_text(request.ctx.message))}"'
    )
