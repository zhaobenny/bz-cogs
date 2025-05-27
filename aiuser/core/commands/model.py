import discord
from redbot.core import app_commands
from discord.app_commands import Group
from typing import Optional
from aiuser.settings.utilities import get_available_models
from .slash_utils import get_config_section


@app_commands.command(
    name="aiuser_model",
    description="Manage or list AI models. Use subcommands: set, get, list.",
)
async def aiuser_model(inter: discord.Interaction):
    await inter.response.send_message(
        "**Subcommands:**\n"
        "`/aiuser_model set <model>` — Set the model for this server or your DMs\n"
        "`/aiuser_model get` — Show the current model\n"
        "`/aiuser_model list` — List available models from this endpoint",
        ephemeral=True,
    )


aiuser_model_group = Group(name="aiuser_model", description="Manage or list AI models.")


@aiuser_model_group.command(name="set", description="Set the AI model for this server or your DMs.")
@app_commands.describe(model="The model to set. Leave blank to clear.")
async def set_model(inter: discord.Interaction, model: Optional[str]):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return

    config_section = get_config_section(cog, inter)

    if inter.guild:
        await config_section.model.set(model)
        context_name = "server"
    else:
        await config_section.dm_model.set(model)
        context_name = "DM"

    await inter.response.send_message(
        f"Set **{context_name}** model to: `{model}`" or "Cleared the model!", ephemeral=True
    )


@aiuser_model_group.command(name="show", description="Show the current AI model for this server or DMs.")
async def show_model(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return

    config_section = get_config_section(cog, inter)

    if inter.guild:
        model = await config_section.model()
        context_name = "server"
    else:
        model = await config_section.dm_model()
        context_name = "DM"

    await inter.response.send_message(f"Current **{context_name}** model: `{model}`", ephemeral=True)


@aiuser_model_group.command(name="list", description="List available models from the current endpoint.")
async def list_models(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog or not hasattr(cog, "openai_client"):
        await inter.response.send_message("Cog or OpenAI client not loaded!", ephemeral=True)
        return

    models = await get_available_models(cog.openai_client)
    if not models:
        await inter.response.send_message("No models available.", ephemeral=True)
        return

    desc = "\n".join(f"{m}" for m in models)
    embed = discord.Embed(
        title="Available models",
        description=desc[:4090] + "..." if len(desc) > 4090 else desc,
        color=discord.Color.blurple(),
    )
    await inter.response.send_message(embed=embed, ephemeral=True)
