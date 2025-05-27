# TODO: turn this into MCP?
import discord
from redbot.core import app_commands
from discord.app_commands import Group
from .slash_utils import get_config_section


@app_commands.command(
    name="aiuser_functions",
    description="Manage function calling.",
)
async def aiuser_functions(inter: discord.Interaction):
    await inter.response.send_message(
        "See the subcommands:\n"
        "/aiuser_functions toggle\n"
        "/aiuser_functions location\n"
        "/aiuser_functions search\n"
        "/aiuser_functions scrape\n"
        "/aiuser_functions weather\n"
        "/aiuser_functions noresponse\n"
        "/aiuser_functions wolframalpha",
        ephemeral=True,
    )


aiuser_functions_group = Group(name="aiuser_functions", description="Manage function calling.")


@aiuser_functions_group.command(name="toggle", description="Toggle function calling.")
async def functions_toggle(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return
    config_section = get_config_section(cog, inter)
    current = await config_section.function_calling()
    toggled = not current
    await config_section.function_calling.set(toggled)
    embed = discord.Embed(
        title="Function Calling now set to:",
        description=f"{toggled}",
        color=discord.Color.green() if toggled else discord.Color.red(),
    )
    if toggled:
        embed.set_footer(text="⚠️ Ensure selected model supports function calling!")
    await inter.response.send_message(embed=embed, ephemeral=True)


@aiuser_functions_group.command(name="location", description="Set the location for function calling.")
@app_commands.describe(latitude="Latitude", longitude="Longitude")
async def functions_location(inter: discord.Interaction, latitude: float, longitude: float):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return
    config_section = get_config_section(cog, inter)
    await config_section.function_calling_default_location.set([latitude, longitude])
    embed = discord.Embed(
        title="Location now set to:",
        description=f"{latitude}, {longitude}",
        color=discord.Color.blurple(),
    )
    await inter.response.send_message(embed=embed, ephemeral=True)


async def toggle_function_helper(config_section, tool_names):
    enabled_tools = await config_section.function_calling_functions() or []
    changed = False
    for tool in tool_names:
        if tool not in enabled_tools:
            enabled_tools.append(tool)
            changed = True
        else:
            enabled_tools.remove(tool)
            changed = True
    await config_section.function_calling_functions.set(enabled_tools)
    return tool_names[0] in enabled_tools, changed


@aiuser_functions_group.command(name="search", description="Toggle Search function.")
async def functions_search(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return
    config_section = get_config_section(cog, inter)
    try:
        from aiuser.functions.search.tool_call import SearchToolCall
    except ImportError:
        await inter.response.send_message("Search function is not available.", ephemeral=True)
        return
    if not (await cog.bot.get_shared_api_tokens("serper")).get("api_key"):
        await inter.response.send_message("Serper.dev key not set!", ephemeral=True)
        return
    tool_names = [SearchToolCall.function_name]
    enabled, _ = await toggle_function_helper(config_section, tool_names)
    await inter.response.send_message(f"Search function enabled: {enabled}", ephemeral=True)


@aiuser_functions_group.command(name="scrape", description="Toggle Scrape function (open URLs).")
async def functions_scrape(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return
    config_section = get_config_section(cog, inter)
    try:
        from aiuser.functions.scrape.tool_call import ScrapeToolCall
    except ImportError:
        await inter.response.send_message("Scrape function is not available.", ephemeral=True)
        return
    tool_names = [ScrapeToolCall.function_name]
    enabled, _ = await toggle_function_helper(config_section, tool_names)
    await inter.response.send_message(f"Scrape function enabled: {enabled}", ephemeral=True)


@aiuser_functions_group.command(name="weather", description="Toggle Weather functions.")
async def functions_weather(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return
    config_section = get_config_section(cog, inter)
    try:
        from aiuser.functions.weather.tool_call import (
            IsDaytimeToolCall,
            LocalWeatherToolCall,
            LocationWeatherToolCall,
        )
    except ImportError:
        await inter.response.send_message("Weather functions are not available.", ephemeral=True)
        return
    tool_names = [
        IsDaytimeToolCall.function_name,
        LocalWeatherToolCall.function_name,
        LocationWeatherToolCall.function_name,
    ]
    enabled, _ = await toggle_function_helper(config_section, tool_names)
    await inter.response.send_message(f"Weather functions enabled: {enabled}", ephemeral=True)


@aiuser_functions_group.command(name="noresponse", description="Toggle the 'No Response' function.")
async def functions_noresponse(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return
    config_section = get_config_section(cog, inter)
    try:
        from aiuser.functions.noresponse.tool_call import NoResponseToolCall
    except ImportError:
        await inter.response.send_message("NoResponse function is not available.", ephemeral=True)
        return
    tool_names = [NoResponseToolCall.function_name]
    enabled, _ = await toggle_function_helper(config_section, tool_names)
    await inter.response.send_message(f"No Response function enabled: {enabled}", ephemeral=True)


@aiuser_functions_group.command(name="wolframalpha", description="Toggle Wolfram Alpha function.")
async def functions_wolframalpha(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return
    config_section = get_config_section(cog, inter)
    try:
        from aiuser.functions.wolframalpha.tool_call import WolframAlphaFunctionCall
    except ImportError:
        await inter.response.send_message("Wolfram Alpha function is not available.", ephemeral=True)
        return
    if not (await cog.bot.get_shared_api_tokens("wolfram_alpha")).get("app_id"):
        await inter.response.send_message("Wolfram Alpha app id not set!", ephemeral=True)
        return
    tool_names = [WolframAlphaFunctionCall.function_name]
    enabled, _ = await toggle_function_helper(config_section, tool_names)
    await inter.response.send_message(f"Wolfram Alpha function enabled: {enabled}", ephemeral=True)
