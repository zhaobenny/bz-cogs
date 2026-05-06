from aiuser.functions.discord.info import DISCORD_INFO_TYPES, get_discord_info
from aiuser.functions.discord.reaction import add_reaction
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema


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
        return await add_reaction(request, arguments.get("emoji", ""))


class GetDiscordInfoToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name="get_discord_info",
            description=(
                "Surface information about certain Discord entities in the current context. "
            ),
            parameters=Parameters(
                properties={
                    "info": {
                        "type": "string",
                        "enum": list(DISCORD_INFO_TYPES),
                        "description": (
                            "The Discord info to fetch. One of: channel, server, "
                            "author, server_emojis."
                        ),
                    },
                },
                required=["info"],
            ),
        )
    )
    function_name = schema.function.name

    async def _handle(self, request, arguments):
        return await get_discord_info(request, arguments.get("info", ""))
