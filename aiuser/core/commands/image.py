import importlib
import discord
from redbot.core import app_commands
from aiuser.config.models import VISION_SUPPORTED_MODELS
from aiuser.types.enums import ScanImageMode
from discord.app_commands import Group
from .slash_utils import get_config_section

aiuser_image_group = Group(
    name="aiuser_image",
    description="Manage image scan and image-to-text AI settings.",
)


@aiuser_image_group.command(name="toggle", description="Toggle image scanning on/off.")
async def image_toggle(inter: discord.Interaction):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return
    config_section = get_config_section(cog, inter)
    value = not (await config_section.scan_images())
    await config_section.scan_images.set(value)
    embed = discord.Embed(
        title="Image Scanning now set to:",
        description=f"`{value}`",
        color=discord.Color.green() if value else discord.Color.red(),
    )
    await inter.response.send_message(embed=embed, ephemeral=True)


@aiuser_image_group.command(name="maxsize", description="Set max image size in MB.")
@app_commands.describe(size="Max download size in Megabytes")
async def image_maxsize(inter: discord.Interaction, size: float):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return
    config_section = get_config_section(cog, inter)
    await config_section.max_image_size.set(size * 1024 * 1024)
    embed = discord.Embed(
        title="Max image download size now set to:",
        description=f"`{size:.2f}` MB",
        color=discord.Color.blurple(),
    )
    await inter.response.send_message(embed=embed, ephemeral=True)


@aiuser_image_group.command(name="mode", description="Set method for scanning images.")
@app_commands.describe(mode="Image scan mode: local, ai-horde, llm")
async def image_mode(inter: discord.Interaction, mode: str):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return

    config_section = get_config_section(cog, inter)
    values = [m.value for m in ScanImageMode]
    mode = mode.lower()

    if mode not in values:
        await inter.response.send_message(f"Invalid mode. Valid modes: {', '.join(values)}", ephemeral=True)
        return

    mode_enum = ScanImageMode(mode)
    if mode_enum == ScanImageMode.LOCAL:
        try:
            importlib.import_module("pytesseract")
            importlib.import_module("torch")
            importlib.import_module("transformers")
            await config_section.scan_images_mode.set(ScanImageMode.LOCAL.value)
            embed = discord.Embed(
                title="Scanning Images now set to LOCAL (CPU heavy!)",
                color=discord.Color.orange(),
            )
            embed.add_field(name="❗ __WILL CAUSE HEAVY CPU LOAD__ ❗", value="`local`", inline=False)
            await inter.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            await config_section.scan_images_mode.set(ScanImageMode.AI_HORDE.value)
            await inter.response.send_message(
                "Local image processing dependencies not available. Please install them to use this feature locally.",
                ephemeral=True,
            )
    elif mode_enum == ScanImageMode.AI_HORDE:
        await config_section.scan_images_mode.set(ScanImageMode.AI_HORDE.value)
        embed = discord.Embed(
            title="Scanning Images now set to AI-Horde",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="👁️ __PRIVACY WARNING__",
            value="This will send image attachments to a random volunteer worker machine for processing!",
            inline=False,
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
    elif mode_enum == ScanImageMode.LLM:
        await config_section.scan_images_mode.set(ScanImageMode.LLM.value)
        model = await config_section.model()
        embed = discord.Embed(
            title="Scanning Images now set to LLM endpoint.",
            description=f"Model: `{model}`",
            color=discord.Color.green(),
        )
        if model not in VISION_SUPPORTED_MODELS:
            embed.add_field(
                name=":warning: Unvalidated Model",
                value=f"Set to `{model}` but not validated for image scanning.",
                inline=False,
            )
        await config_section.scan_images_model.set(model)
        await inter.response.send_message(embed=embed, ephemeral=True)


@aiuser_image_group.command(name="model", description="Set the specific LLM model for image scan.")
@app_commands.describe(model_name="Name of a compatible model")
async def image_model(inter: discord.Interaction, model_name: str):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return

    config_section = get_config_section(cog, inter)
    await config_section.scan_images_model.set(model_name)
    embed = discord.Embed(
        title="LLM for image scan now set to:",
        description=f"`{model_name}`",
        color=discord.Color.green(),
    )
    await inter.response.send_message(embed=embed, ephemeral=True)
