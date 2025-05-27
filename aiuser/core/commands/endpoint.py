import discord
from redbot.core import app_commands
from ..openai_utils import setup_openai_client
from .slash_utils import owner_check
from typing import Optional
import logging
import httpx

logger = logging.getLogger("red.bz_cogs.aiuser")


@app_commands.command(
    name="aiuser_endpoint",
    description="Set or update the OpenAI API endpoint.",
)
@app_commands.describe(
    url="Custom OpenAI API compatible endpoint URL, or 'openai', 'openrouter', 'ollama', 'grok'.",
    api_key="(Optional) API key for this endpoint.",
)
@owner_check()
async def aiuser_endpoint(inter: discord.Interaction, url: Optional[str], api_key: Optional[str] = None):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("AIUser Cog not loaded!", ephemeral=True)
        return

    if not hasattr(cog, "bot") or not hasattr(cog, "config") or not hasattr(cog, "openai_client"):
        err_msg = "AIUser Cog is missing critical attributes (bot, config, or openai_client)."
        logger.error(err_msg)
        await inter.response.send_message(err_msg, ephemeral=True)
        return

    if not inter.response.is_done():
        await inter.response.defer(ephemeral=True, thinking=True)

    orig_input_url = url
    endpoint_type = "openai"

    if url == "openrouter":
        url = "https://openrouter.ai/api/v1/"
        endpoint_type = "openrouter"
    elif url == "ollama":
        url = "http://localhost:11434/v1/"
        endpoint_type = "ollama"
    elif url in ("openai", None, "", "clear", "reset"):
        url = "https://api.openai.com/v1/"
        endpoint_type = "openai"
    else:
        url_lower = (url or "").lower()
        if "openrouter" in url_lower:
            endpoint_type = "openrouter"
        elif "ollama" in url_lower:
            endpoint_type = "ollama"
        elif "grok" in url_lower:
            endpoint_type = "grok"
        else:
            endpoint_type = "openai-like"

    if api_key is None:
        # TODO: add env checks to see if the respected API key type is in the env or as a redbot api
        if endpoint_type == "openai":
            try:
                cog.openai_client = await setup_openai_client(cog.bot, cog.config)
                if not cog.openai_client:
                    raise ConnectionError("Client setup returned None.")
            except Exception as e_setup:
                logger.error(f"Failed to setup client for endpoint '{url}': {e_setup}", exc_info=True)

                await inter.followup.send(
                    f":warning: Failed to initialize client for `{orig_input_url or 'default'}`. Endpoint reverted. Error: {e_setup}",
                    ephemeral=True,
                )
                return

        elif endpoint_type == "ollama":
            async with httpx.AsyncClient() as client:
                r = await client.get(url + "models")
                if r.status_code != 200:
                    raise RuntimeError(f"Ollama error: {r.text}")
        elif endpoint_type == "openrouter":
            async with httpx.AsyncClient() as client:
                r = await client.get(url + "models")
                if r.status_code != 200:
                    raise RuntimeError(f"OpenRouter error: {r.text}")
        elif endpoint_type == "grok":
            # check for XAI_API_KEY, for now pass
            pass
        else:  # endpoint_type openai-like
            pass

    success_message = f"✅ Endpoint set to `{url or 'Official OpenAI'}` successfully.\n"
    if api_key is not None:
        success_message += "API key updated for this endpoint.\n"
    else:
        success_message += "API key was not changed.\n"

    success_message += "You may need to set your model for this endpoint using `/aiuser model`."

    embed = discord.Embed(title="Endpoint Updated", description=success_message, color=discord.Color.green())
    await inter.followup.send(embed=embed, ephemeral=True)
