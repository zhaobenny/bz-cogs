import discord
from redbot.core import app_commands
from aiuser.core.handlers import handle_slash_command
from .commands.prompt import aiuser_prompt_group
from .commands.model import aiuser_model_group
from .commands.functions import aiuser_functions_group
from .commands.image import aiuser_image_group
from .commands.slash_utils import get_owner_ids, owner_check
from .commands.endpoint import aiuser_endpoint
from ..response.chat.response import remove_patterns_from_response


@app_commands.command(name="chat", description="Talk directly to this bot's AI. Ask it anything you want!")
@app_commands.describe(text="The prompt you want to send to the AI.")
@app_commands.checks.cooldown(1, 30)
async def chat_slash_command(inter: discord.Interaction, text: str):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        if not inter.response.is_done():
            await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return

    member = inter.user
    is_nitro = bool(getattr(member, "premium_since", None) or getattr(member, "premium_type", 0))
    max_length = 4000 if is_nitro else 2000

    if not (1 <= len(text) <= max_length):
        if not inter.response.is_done():
            await inter.response.send_message(f"Text must be between 1 and {max_length} characters.", ephemeral=True)
        return

    raw_response = await handle_slash_command(cog, inter, text)
    if not raw_response or not isinstance(raw_response, str):
        if not inter.response.is_done():
            await inter.response.send_message("No response generated.", ephemeral=True)
        return

    cleaned_response = await remove_patterns_from_response(inter, cog.config, raw_response)
    if not cleaned_response or not isinstance(cleaned_response, str) or not cleaned_response.strip():
        if not inter.response.is_done():
            await inter.response.send_message("Response was empty after cleaning.", ephemeral=True)
        return

    if not inter.response.is_done():
        await inter.response.send_message(cleaned_response, ephemeral=False)


@app_commands.command(
    name="aiuser_accepted",
    description="Manage the accepted admin IDs.",
)
@app_commands.describe(
    action="What to do: view/add/remove",
    user="The user to add/remove (mention or user ID, required for add/remove)",
)
@owner_check()
async def aiuser_accepted_slash_command(
    inter: discord.Interaction,
    action: str,
    user: discord.User = None,
):
    cog = inter.client.get_cog("AIUser")
    if not cog:
        await inter.response.send_message("Cog not loaded!", ephemeral=True)
        return

    owner_ids = await get_owner_ids(inter)
    if inter.user.id not in owner_ids:
        await inter.response.send_message("Only the owner can manage accepted IDs.", ephemeral=True)
        return

    accepted_ids = set(await cog.config.accepted_ids() or [])

    if action.lower() == "view":
        ids_display = list(owner_ids) + [uid for uid in accepted_ids if uid not in owner_ids]
        await inter.response.send_message(
            "Accepted admin user IDs:\n" + "\n".join(f"- <@{uid}> (`{uid}`)" for uid in ids_display),
            ephemeral=True,
        )
        return

    if action.lower() == "add":
        if not user:
            await inter.response.send_message(
                "You must mention a user or provide their user ID to add.", ephemeral=True
            )
            return
        accepted_ids.add(user.id)
        await cog.config.accepted_ids.set(list(accepted_ids))
        await inter.response.send_message(f"Added <@{user.id}> (`{user.id}`) to accepted admin IDs.", ephemeral=True)
        return

    if action.lower() == "remove":
        if not user:
            await inter.response.send_message(
                "You must mention a user or provide their user ID to remove.", ephemeral=True
            )
            return
        if user.id in owner_ids:
            await inter.response.send_message("You cannot remove the owner from accepted IDs.", ephemeral=True)
            return
        accepted_ids.discard(user.id)
        await cog.config.accepted_ids.set(list(accepted_ids))
        await inter.response.send_message(
            f"Removed <@{user.id}> (`{user.id}`) from accepted admin IDs.", ephemeral=True
        )
        return

    await inter.response.send_message("Invalid action. Use view, add, or remove.", ephemeral=True)


async def app_install(bot, cog):
    tree = cog.bot if hasattr(cog, "bot") else bot
    tree.tree.add_command(chat_slash_command)
    tree.tree.add_command(aiuser_prompt_group)
    tree.tree.add_command(aiuser_model_group)
    tree.tree.add_command(aiuser_accepted_slash_command)
    tree.tree.add_command(aiuser_functions_group)
    tree.tree.add_command(aiuser_image_group)
    tree.tree.add_command(aiuser_endpoint)

    try:
        from discord.app_commands import installs

        chat_slash_command.allowed_contexts = installs.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        )
        chat_slash_command.allowed_installs = installs.AppInstallationType(guild=True, user=True)

        aiuser_accepted_slash_command.allowed_contexts = installs.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        )
        aiuser_accepted_slash_command.allowed_installs = installs.AppInstallationType(guild=True, user=True)

        for group in [
            aiuser_prompt_group,
            aiuser_model_group,
            aiuser_functions_group,
            aiuser_image_group,
            aiuser_endpoint,
        ]:
            group.allowed_contexts = installs.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
            group.allowed_installs = installs.AppInstallationType(guild=True, user=True)
            for subcmd in group.commands:
                subcmd.allowed_contexts = installs.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
                subcmd.allowed_installs = installs.AppInstallationType(guild=True, user=True)
    except Exception as e:
        print(f"Error setting command contexts/installs: {e}")
