import logging
from textwrap import shorten

import discord
from emoji import EMOJI_DATA

from aiuser.context.converter.formatters import mention_to_text
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


def _message_preview(content: str) -> str:
    preview = " ".join(content.split())
    return shorten(preview, width=48, placeholder="...") or "[no text content]"


def _parse_custom_emoji(bot, value: str):
    parsed = discord.PartialEmoji.from_str(value)
    if not parsed.id:
        return None
    return discord.utils.get(bot.emojis, name=parsed.name, id=parsed.id)


class AddReactionToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name="add_reaction",
            description=(
                "Adds one reaction emoji to the Discord message that invoked a response."
            ),
            parameters=Parameters(
                properties={
                    "emoji": {
                        "type": "string",
                        "description": (
                            "Exactly one Unicode emoji, or one raw custom Discord "
                            "emoji such as <:name:id> or <a:name:id>."
                        ),
                    },
                },
                required=["emoji"],
            ),
        )
    )
    function_name = schema.function.name

    async def _handle(self, request, arguments):
        emoji = str(arguments.get("emoji", "")).strip()

        if request.ctx.interaction:
            return "Cannot add reaction during slash command interactions."

        if emoji in EMOJI_DATA:
            reaction = emoji
        else:
            reaction = _parse_custom_emoji(request.bot, emoji)

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
            f'Added reaction {emoji} to the message: '
            f'"{_message_preview(mention_to_text(request.ctx.message))}"'
        )
