import discord
from redbot.core import commands

from aiuser.config.defaults import DEFAULT_TOOL_CALL_ROUNDS
from aiuser.functions import names
from aiuser.speech.tts import DEFAULT_MODELS, DEFAULT_VOICES
from aiuser.config.model_info import get_model_info
from aiuser.settings.functions.imagerequest import ImageRequestFunctionSettings
from aiuser.settings.functions.memory import MemoryFunctionSettings
from aiuser.settings.functions.searxng import SearXNGFunctionSettings
from aiuser.settings.functions.utilities import (
    FunctionsGroupMixin,
    functions,
    provider_key_error,
)
from aiuser.settings.functions.voice import VoiceFunctionSettings
from aiuser.settings.functions.weather import WeatherFunctionSettings


class FunctionCallingSettings(
    FunctionsGroupMixin,
    WeatherFunctionSettings,
    ImageRequestFunctionSettings,
    VoiceFunctionSettings,
    SearXNGFunctionSettings,
    MemoryFunctionSettings,
):
    @functions.command(name="toggle")
    async def toggle_function_calling(self, ctx: commands.Context):
        """Toggle functions calling

        Requires a model that is whitelisted or supported for function calling
        If enabled, the LLM will call functions to generate responses when needed
        This will generate additional API calls and token usage!

        """

        current_value = not await self.config.guild(ctx.guild).function_calling()
        await self.config.guild(ctx.guild).function_calling.set(current_value)

        embed = discord.Embed(
            title="Functions Calling now set to:",
            description=f"{current_value}",
            color=await ctx.embed_color(),
        )

        current_model = await self.config.guild(ctx.guild).model()
        if current_value and not get_model_info(current_model).supports_tools:
            embed.set_footer(text="⚠️ Ensure selected model supports function calling!")
        await ctx.send(embed=embed)

    @functions.command(name="config", aliases=["show", "settings"])
    async def functions_config(self, ctx: commands.Context):
        """Show function calling configuration overview."""
        guild_conf = self.config.guild(ctx.guild)
        enabled = await guild_conf.function_calling()
        enabled_tools: list = await guild_conf.function_calling_functions() or []
        tool_call_rounds = (
            await guild_conf.function_calling_tool_call_rounds()
            or DEFAULT_TOOL_CALL_ROUNDS
        )

        groups = {
            "Weather": [names.IS_DAYTIME, names.GET_WEATHER],
            "Image Request": [names.IMAGE_REQUEST],
            "Voice Request": [names.VOICE_REQUEST],
            "Serper": [names.SEARCH_GOOGLE],
            "SearXNG": [names.SEARXNG],
            "Scrape": [names.OPEN_URL],
            "No Response": [names.DO_NOT_RESPOND],
            "Wolfram Alpha": [names.ASK_WOLFRAM_ALPHA],
            "Code Runner": [names.RUN_PYTHON_CODE],
            "Memory": [names.READ_MEMORY, names.SAVE_MEMORY],
            "Discord": [names.ADD_REACTION, names.GET_DISCORD_INFO],
        }

        # Helper for status icon
        def icon(active: bool) -> str:
            return "✅" if active else "❌"

        total_tools = sum(len(v) for v in groups.values())
        enabled_count = sum(1 for v in groups.values() for t in v if t in enabled_tools)

        # Summary / main embed
        colour = await ctx.embed_color()
        main_embed = discord.Embed(title="Function Calling Settings", color=colour)
        main_embed.add_field(name="Enabled", value=f"{icon(enabled)}", inline=True)

        # Spacer to keep grid layout consistent
        main_embed.add_field(name="\u200b", value="\u200b", inline=True)
        main_embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Overview of each group (compact)
        # Only show a checkmark for whether the group has any enabled tools.
        for group_name, tool_names in groups.items():
            group_enabled = any(t in enabled_tools for t in tool_names)
            main_embed.add_field(
                name=group_name, value=icon(group_enabled), inline=True
            )

        # Summary line
        main_embed.add_field(
            name="Totals",
            value=f"Enabled tools: **`{enabled_count}/{total_tools}`**",
            inline=False,
        )
        main_embed.add_field(
            name="Tool Call Rounds",
            value=f"`{tool_call_rounds}`",
            inline=False,
        )

        embeds = [main_embed]

        image_tools = groups["Image Request"]
        image_enabled = any(t in enabled_tools for t in image_tools)
        image_endpoint = (
            await guild_conf.function_calling_image_custom_endpoint() or "Autodetected"
        )
        image_model = await guild_conf.function_calling_image_model() or "Default"
        image_preprompt = await guild_conf.function_calling_image_preprompt()
        preprompt_display = image_preprompt or "(None)"
        if len(preprompt_display) > 500:
            preprompt_display = preprompt_display[:497] + "..."

        image_embed = discord.Embed(
            title="Image Request Function Settings", color=colour
        )
        image_embed.add_field(
            name="Enabled", value=f"{icon(image_enabled)}", inline=True
        )
        image_embed.add_field(
            name="Custom Endpoint", value=f"`{image_endpoint}`", inline=True
        )
        image_embed.add_field(name="Model", value=f"`{image_model}`", inline=True)
        image_embed.add_field(
            name="Preprompt", value=f"```{preprompt_display}```", inline=False
        )
        if image_enabled:
            embeds.append(image_embed)

        voice_tools = groups["Voice Request"]
        voice_enabled = any(t in enabled_tools for t in voice_tools)
        voice_provider = await guild_conf.function_calling_voice_provider()
        voice_provider_key = voice_provider.strip().lower()
        default_voice_model = DEFAULT_MODELS.get(voice_provider_key)
        voice_model = (
            await guild_conf.function_calling_voice_model() or default_voice_model
        )
        default_voice = DEFAULT_VOICES.get(voice_provider_key)
        voice_name = await guild_conf.function_calling_voice() or default_voice

        voice_embed = discord.Embed(
            title="Voice Request Function Settings", color=colour
        )
        voice_embed.add_field(
            name="Enabled", value=f"{icon(voice_enabled)}", inline=True
        )
        voice_embed.add_field(name="Provider", value=f"`{voice_provider}`", inline=True)
        voice_embed.add_field(name="Model", value=f"`{voice_model}`", inline=True)
        voice_embed.add_field(name="Voice", value=f"`{voice_name}`", inline=True)
        if voice_enabled:
            embeds.append(voice_embed)

        for em in embeds:
            await ctx.send(embed=em)
        return

    @functions.group(name="discord")
    async def functions_discord(self, ctx: commands.Context):
        """Configure native Discord action functions."""
        pass

    @functions_discord.command(name="react", aliases=["reaction"])
    async def toggle_discord_reaction_function(self, ctx: commands.Context):
        """Enable/disable the functionality for adding reactions to triggering Discord messages."""
        tool_names = [names.ADD_REACTION]
        enabled_tools: list = await self.config.guild(
            ctx.guild
        ).function_calling_functions()
        new_state = names.ADD_REACTION not in enabled_tools

        if new_state:
            enabled_tools.extend(tool_names)
        else:
            for tool in tool_names:
                if tool in enabled_tools:
                    enabled_tools.remove(tool)

        await self.config.guild(ctx.guild).function_calling_functions.set(enabled_tools)

        embed = discord.Embed(
            title="Discord reaction function calling now set to:",
            description=f"{new_state}",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @functions_discord.command(name="info")
    async def toggle_discord_info_function(self, ctx: commands.Context):
        """Enable/disable the functionality for reading some select Discord channel, server, author, and emoji info."""
        tool_names = [names.GET_DISCORD_INFO]
        await self.toggle_function_group(ctx, tool_names, "Discord info")

    @functions.command(name="maxrounds", aliases=["maxcalls"])
    async def functions_max_rounds(self, ctx: commands.Context, rounds: int):
        """Set the maximum number of tool call rounds per response."""
        if rounds < 1:
            return await ctx.react_quietly("❌")

        await self.config.guild(ctx.guild).function_calling_tool_call_rounds.set(rounds)

        embed = discord.Embed(
            title="Function calling tool call rounds now set to:",
            description=f"`{rounds}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @functions.command(name="serper")
    async def toggle_serper_function(self, ctx: commands.Context):
        """Enable/disable searching/scraping the Internet using Serper.dev"""
        key_error = await provider_key_error(self.bot, ctx, "serper")
        if key_error:
            return await ctx.send(key_error)

        tool_names = [names.SEARCH_GOOGLE]
        await self.toggle_function_group(ctx, tool_names, "Search")

    @functions.command(name="scrape")
    async def toggle_scrape_function(self, ctx: commands.Context):
        """
        Enable/disable the functionality for the LLM to open URLs in messages

        (May not be called if the link generated an Discord embed)
        """
        tool_names = [names.OPEN_URL]
        await self.toggle_function_group(ctx, tool_names, "Scrape")

    @functions.command(name="noresponse")
    async def toggle_ignore_function(self, ctx: commands.Context):
        """
        Enable/disable the functionality for the LLM to choose to not respond and ignore messages.

        Temperamental, may require additional prompting to work better.
        """
        tool_names = [names.DO_NOT_RESPOND]
        await self.toggle_function_group(ctx, tool_names, "No response")

    @functions.command(name="wolframalpha")
    async def toggle_wolfram_alpha_function(self, ctx: commands.Context):
        """Enable/disable the functionality for the LLM to ask Wolfram Alpha about math, exchange rates, or the weather."""
        key_error = await provider_key_error(self.bot, ctx, "wolfram_alpha", key_name="app_id")
        if key_error:
            return await ctx.send(key_error)

        tool_names = [names.ASK_WOLFRAM_ALPHA]
        await self.toggle_function_group(ctx, tool_names, "Wolfram Alpha")

    @functions.command(name="modalcoderunner")
    async def toggle_modal_function(self, ctx: commands.Context):
        """Enable/disable the functionality for the LLM to run Python code in a ephemeral environment backed by Modal."""
        tokens = await self.bot.get_shared_api_tokens("modal")
        if not tokens.get("token_id") and not tokens.get("token_secret"):
            return await ctx.send(
                f"[Modal.com](https://modal.com/settings/) API Token not set! Set them using: \n`{ctx.clean_prefix}set api modal token_id,TOKENID` \n`{ctx.clean_prefix}set api modal token_secret,TOKENSECRET`.",
                suppress_embeds=True,
            )

        tool_names = [names.RUN_PYTHON_CODE]
        await self.toggle_function_group(ctx, tool_names, "Modal Code Runner")
