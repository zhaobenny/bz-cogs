import discord
from redbot.core import commands

from aiuser.config.defaults import DEFAULT_TOOL_CALL_ROUNDS
from aiuser.config.model_info import get_model_info
from aiuser.functions import names
from aiuser.settings.functions.imagerequest import ImageRequestFunctionSettings
from aiuser.settings.functions.memory import MemoryFunctionSettings
from aiuser.settings.functions.scrape import ScrapeFunctionSettings
from aiuser.settings.functions.search import SearchFunctionSettings
from aiuser.settings.functions.utilities import (
    FunctionsGroupMixin,
    functions,
    provider_key_error,
)
from aiuser.settings.functions.view import (
    ToolSettingsView,
    load_tool_settings_snapshot,
)
from aiuser.settings.functions.voice import VoiceFunctionSettings
from aiuser.settings.functions.weather import WeatherFunctionSettings


class FunctionCallingSettings(
    FunctionsGroupMixin,
    WeatherFunctionSettings,
    ImageRequestFunctionSettings,
    VoiceFunctionSettings,
    SearchFunctionSettings,
    ScrapeFunctionSettings,
    MemoryFunctionSettings,
):
    @functions.command(name="enable")
    async def enable_function_calling(self, ctx: commands.Context):
        """Allow the model to use configured tools."""
        return await self._set_function_calling(ctx, True)

    @functions.command(name="disable")
    async def disable_function_calling(self, ctx: commands.Context):
        """Prevent the model from using tools without changing tool selections."""
        return await self._set_function_calling(ctx, False)

    async def _set_function_calling(self, ctx: commands.Context, enabled: bool):
        await self.config.guild(ctx.guild).function_calling.set(enabled)
        embed = discord.Embed(
            title="Tool use is now:",
            description="Enabled" if enabled else "Disabled",
            color=await ctx.embed_color(),
        )

        current_model = (
            await self.config.guild(ctx.guild).model()
            or await self.config.default_model()
        )
        if enabled and not get_model_info(current_model).supports_tools:
            embed.set_footer(text="⚠️ Ensure the selected model supports tools!")
        return await ctx.send(embed=embed)

    @functions.command(name="status", aliases=["config", "show", "settings"])
    async def functions_config(self, ctx: commands.Context):
        """Show and manage tool configuration."""
        color = await ctx.embed_color()
        snapshot = await load_tool_settings_snapshot(self, ctx.guild)
        view = ToolSettingsView(self, ctx, color, snapshot)
        view.message = await ctx.send(embed=view.build_embed(), view=view)

    @functions.group(name="discord")
    async def functions_discord(self, ctx: commands.Context):
        """Configure native Discord tools."""

    @functions_discord.command(name="show")
    async def show_discord_functions(self, ctx: commands.Context):
        """Show native Discord tool settings."""
        enabled_tools: list = await self.config.guild(
            ctx.guild
        ).function_calling_functions()
        embed = discord.Embed(
            title="Discord tool settings", color=await ctx.embed_color()
        )
        embed.add_field(
            name="Reactions",
            value="Enabled" if names.ADD_REACTION in enabled_tools else "Disabled",
        )
        embed.add_field(
            name="Information",
            value="Enabled" if names.GET_DISCORD_INFO in enabled_tools else "Disabled",
        )
        return await ctx.send(embed=embed)

    @functions_discord.group(name="reactions", aliases=["react", "reaction"])
    async def functions_discord_reactions(self, _):
        """Configure the Discord reaction tool."""

    @functions_discord_reactions.command(name="enable")
    async def enable_discord_reaction_function(self, ctx: commands.Context):
        """Allow the model to add reactions to triggering messages."""
        return await self.set_function_group(
            ctx, [names.ADD_REACTION], "Discord reactions", True
        )

    @functions_discord_reactions.command(name="disable")
    async def disable_discord_reaction_function(self, ctx: commands.Context):
        """Prevent the model from adding reactions."""
        return await self.set_function_group(
            ctx, [names.ADD_REACTION], "Discord reactions", False
        )

    @functions_discord.group(name="info")
    async def functions_discord_info(self, _):
        """Configure the Discord information tool."""

    @functions_discord_info.command(name="enable")
    async def enable_discord_info_function(self, ctx: commands.Context):
        """Allow the model to read selected Discord context."""
        return await self.set_function_group(
            ctx, [names.GET_DISCORD_INFO], "Discord information", True
        )

    @functions_discord_info.command(name="disable")
    async def disable_discord_info_function(self, ctx: commands.Context):
        """Prevent the model from reading additional Discord context."""
        return await self.set_function_group(
            ctx, [names.GET_DISCORD_INFO], "Discord information", False
        )

    @functions.group(
        name="max_rounds",
        aliases=["maxrounds", "maxcalls"],
        invoke_without_command=True,
    )
    async def functions_max_rounds(self, ctx: commands.Context):
        """Show the maximum tool-call rounds per response."""
        rounds = (
            await self.config.guild(ctx.guild).function_calling_tool_call_rounds()
            or DEFAULT_TOOL_CALL_ROUNDS
        )
        return await ctx.maybe_send_embed(f"Maximum tool-call rounds: `{rounds}`")

    @functions_max_rounds.command(name="set")
    async def functions_max_rounds_set(self, ctx: commands.Context, rounds: int):
        """Set the maximum number of tool call rounds per response."""
        if rounds < 1:
            return await ctx.maybe_send_embed("Please enter a positive number.")

        await self.config.guild(ctx.guild).function_calling_tool_call_rounds.set(rounds)
        return await ctx.maybe_send_embed(
            f"Maximum tool-call rounds set to `{rounds}`."
        )

    @functions.group(
        name="no_response", aliases=["noresponse"], invoke_without_command=True
    )
    async def ignore_function(self, ctx: commands.Context):
        """Show whether the no-response tool is enabled."""
        return await self.show_function_group(
            ctx, [names.DO_NOT_RESPOND], "No response"
        )

    @ignore_function.command(name="enable")
    async def enable_ignore_function(self, ctx: commands.Context):
        """Allow the model to choose not to respond."""
        return await self.set_function_group(
            ctx, [names.DO_NOT_RESPOND], "No response", True
        )

    @ignore_function.command(name="disable")
    async def disable_ignore_function(self, ctx: commands.Context):
        """Require the model to produce a response when triggered."""
        return await self.set_function_group(
            ctx, [names.DO_NOT_RESPOND], "No response", False
        )

    @functions.group(
        name="wolfram_alpha", aliases=["wolframalpha"], invoke_without_command=True
    )
    async def wolfram_alpha_function(self, ctx: commands.Context):
        """Show whether the Wolfram Alpha tool is enabled."""
        return await self.show_function_group(
            ctx, [names.ASK_WOLFRAM_ALPHA], "Wolfram Alpha"
        )

    @wolfram_alpha_function.command(name="enable")
    async def enable_wolfram_alpha_function(self, ctx: commands.Context):
        """Allow the model to query Wolfram Alpha."""
        key_error = await provider_key_error(
            self.bot, ctx, "wolfram_alpha", key_name="app_id"
        )
        if key_error:
            return await ctx.maybe_send_embed(key_error)
        return await self.set_function_group(
            ctx, [names.ASK_WOLFRAM_ALPHA], "Wolfram Alpha", True
        )

    @wolfram_alpha_function.command(name="disable")
    async def disable_wolfram_alpha_function(self, ctx: commands.Context):
        """Prevent the model from querying Wolfram Alpha."""
        return await self.set_function_group(
            ctx, [names.ASK_WOLFRAM_ALPHA], "Wolfram Alpha", False
        )

    @functions.group(
        name="code_runner", aliases=["modalcoderunner"], invoke_without_command=True
    )
    async def code_runner_function(self, ctx: commands.Context):
        """Show whether the Python code runner is enabled."""
        return await self.show_function_group(
            ctx, [names.RUN_PYTHON_CODE], "Code runner"
        )

    @code_runner_function.command(name="enable")
    async def enable_code_runner_function(self, ctx: commands.Context):
        """Allow the model to run Python code through Modal."""
        tokens = await self.bot.get_shared_api_tokens("modal")
        if not tokens.get("token_id") and not tokens.get("token_secret"):
            return await ctx.maybe_send_embed(
                f"[Modal.com](<https://modal.com/settings/>) API Token not set! Set them using: \n`{ctx.clean_prefix}set api modal token_id,TOKENID` \n`{ctx.clean_prefix}set api modal token_secret,TOKENSECRET`."
            )
        return await self.set_function_group(
            ctx, [names.RUN_PYTHON_CODE], "Code runner", True
        )

    @code_runner_function.command(name="disable")
    async def disable_code_runner_function(self, ctx: commands.Context):
        """Prevent the model from running Python code."""
        return await self.set_function_group(
            ctx, [names.RUN_PYTHON_CODE], "Code runner", False
        )
