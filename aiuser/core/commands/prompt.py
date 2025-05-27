import discord
from redbot.core import app_commands
from discord.app_commands import Group, locale_str
from aiuser.config.defaults import DEFAULT_PROMPT, DEFAULT_DM_PROMPT
from typing import Optional


aiuser_prompt_group = Group(
    name="aiuser_prompt", description=locale_str("Manage or set the AI prompt."), guild_only=False
)


@aiuser_prompt_group.command(name="show", description=locale_str("Show the current prompt."))
async def prompt_show(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("AIUser cog not loaded!", ephemeral=True)
        return
    config_section = cog.config.guild(inter.guild) if inter.guild else cog.config.user(inter.user)
    if inter.guild:
        val = await config_section.custom_text_prompt() or await cog.config.custom_text_prompt() or DEFAULT_PROMPT
        await inter.response.send_message(f"**Server prompt:**\n{val}", ephemeral=True)
    else:
        val = await cog.config.dm_prompt() or await cog.config.custom_text_prompt() or DEFAULT_DM_PROMPT
        await inter.response.send_message(f"**DM prompt:**\n{val}", ephemeral=True)


@aiuser_prompt_group.command(name="set", description=locale_str("Set a new prompt."))
@app_commands.describe(prompt=locale_str("The new prompt text. Leave blank to reset to default."))
async def prompt_set(inter: discord.Interaction, prompt: Optional[str]):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("AIUser cog not loaded!", ephemeral=True)
        return
    config_section = cog.config.guild(inter.guild) if inter.guild else cog.config.user(inter.user)
    if inter.guild:
        if not prompt:
            await config_section.custom_text_prompt.set(None)
            await inter.response.send_message("Server prompt reset to default.", ephemeral=True)
        else:
            await config_section.custom_text_prompt.set(prompt)
            await inter.response.send_message(f"Server prompt set:\n{prompt}", ephemeral=True)
    else:
        if not prompt:
            await cog.config.dm_prompt.set(None)
            await inter.response.send_message("DM prompt reset to default.", ephemeral=True)
        else:
            await cog.config.dm_prompt.set(prompt)
            await inter.response.send_message(f"DM prompt set:\n{prompt}", ephemeral=True)
