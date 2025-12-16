import discord
from redbot.core import commands

from aiuser.settings.functions.imagerequest import ImageRequestFunctionSettings
from aiuser.settings.functions.searxng import SearXNGFunctionSettings
from aiuser.settings.functions.utilities import (
    FunctionsGroupMixin,
    functions,
)
from aiuser.settings.functions.weather import WeatherFunctionSettings


class FunctionCallingSettings(
    FunctionsGroupMixin,
    WeatherFunctionSettings,
    ImageRequestFunctionSettings,
    SearXNGFunctionSettings,
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
        if current_value:
            embed.set_footer(text="⚠️ Ensure selected model supports function calling!")
        await ctx.send(embed=embed)

    @functions.command(name="config", aliases=["show", "settings"])
    async def functions_config(self, ctx: commands.Context):
        """Show function calling configuration overview."""
        guild_conf = self.config.guild(ctx.guild)
        enabled = await guild_conf.function_calling()
        enabled_tools: list = await guild_conf.function_calling_functions() or []

        from aiuser.functions.coderunner.tool_call import CodeRunnerToolCall
        from aiuser.functions.imagerequest.tool_call import ImageRequestToolCall
        from aiuser.functions.noresponse.tool_call import NoResponseToolCall
        from aiuser.functions.scrape.tool_call import ScrapeToolCall
        from aiuser.functions.searxng.tool_call import SearXNGToolCall
        from aiuser.functions.serper.tool_call import SerperToolCall
        from aiuser.functions.weather.tool_call import (
            IsDaytimeToolCall,
            LocationWeatherToolCall,
        )
        from aiuser.functions.wolframalpha.tool_call import (
            WolframAlphaFunctionCall,
        )

        groups = {
            "Weather": [
                IsDaytimeToolCall.function_name,
                LocationWeatherToolCall.function_name,
            ],
            "Image Request": [ImageRequestToolCall.function_name],
            "Serper": [SerperToolCall.function_name],
            "SearXNG": [SearXNGToolCall.function_name],
            "Scrape": [ScrapeToolCall.function_name],
            "No Response": [NoResponseToolCall.function_name],
            "Wolfram Alpha": [WolframAlphaFunctionCall.function_name],
            "Code Runner": [CodeRunnerToolCall.function_name],
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

        for em in embeds:
            await ctx.send(embed=em)
        return

    @functions.command(name="serper")
    async def toggle_serper_function(self, ctx: commands.Context):
        """Enable/disable searching/scraping the Internet using Serper.dev"""
        if not (await self.bot.get_shared_api_tokens("serper")).get("api_key"):
            return await ctx.send(
                f"Serper.dev key not set! Set it using `{ctx.clean_prefix}set api serper api_key,APIKEY`."
            )

        from aiuser.functions.serper.tool_call import SerperToolCall

        tool_names = [SerperToolCall.function_name]
        await self.toggle_function_group(ctx, tool_names, "Search")

    @functions.command(name="scrape")
    async def toggle_scrape_function(self, ctx: commands.Context):
        """
        Enable/disable the functionality for the LLM to open URLs in messages

        (May not be called if the link generated an Discord embed)
        """
        from aiuser.functions.scrape.tool_call import ScrapeToolCall

        tool_names = [ScrapeToolCall.function_name]
        await self.toggle_function_group(ctx, tool_names, "Scrape")

    @functions.command(name="noresponse")
    async def toggle_ignore_function(self, ctx: commands.Context):
        """
        Enable/disable the functionality for the LLM to choose to not respond and ignore messages.

        Temperamental, may require additional prompting to work better.
        """
        from aiuser.functions.noresponse.tool_call import NoResponseToolCall

        tool_names = [NoResponseToolCall.function_name]
        await self.toggle_function_group(ctx, tool_names, "No response")

    @functions.command(name="wolframalpha")
    async def toggle_wolfram_alpha_function(self, ctx: commands.Context):
        """Enable/disable the functionality for the LLM to ask Wolfram Alpha about math, exchange rates, or the weather."""
        from aiuser.functions.wolframalpha.tool_call import WolframAlphaFunctionCall

        if not (await self.bot.get_shared_api_tokens("wolfram_alpha")).get("app_id"):
            return await ctx.send(
                f"Wolfram Alpha app id not set! Set it using `{ctx.clean_prefix}set api wolfram_alpha app_id,APPID`."
            )

        tool_names = [WolframAlphaFunctionCall.function_name]
        await self.toggle_function_group(ctx, tool_names, "Wolfram Alpha")

    @functions.command(name="modalcoderunner")
    async def toggle_modal_function(self, ctx: commands.Context):
        """Enable/disable the functionality for the LLM to run Python code in a ephemeral environment backed by Modal."""
        from aiuser.functions.coderunner.tool_call import CodeRunnerToolCall

        tokens = await self.bot.get_shared_api_tokens("modal")
        if not tokens.get("token_id") and not tokens.get("token_secret"):
            return await ctx.send(
                f"[Modal.com](https://modal.com/settings/) API Token not set! Set them using: \n`{ctx.clean_prefix}set api modal token_id,TOKENID` \n`{ctx.clean_prefix}set api modal token_secret,TOKENSECRET`.",
                suppress_embeds=True,
            )

        tool_names = [CodeRunnerToolCall.function_name]
        await self.toggle_function_group(ctx, tool_names, "Modal Code Runner")
