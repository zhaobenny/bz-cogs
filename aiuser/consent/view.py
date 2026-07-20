from __future__ import annotations

import random
from typing import TYPE_CHECKING, Set

import discord

if TYPE_CHECKING:
    from aiuser.consent.service import ConsentService

CONSENT_EMBED_TITLE = ":information_source: AI User Opt-In / Opt-Out"


class ConsentView(discord.ui.View):
    def __init__(self, consent: "ConsentService"):
        super().__init__()
        self.consent = consent

    @discord.ui.button(label="Opt In", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self.consent.opt_in(interaction.user.id):
            return await interaction.response.send_message(
                "You are already opted in.", ephemeral=True
            )
        await interaction.response.send_message(
            "You are now opted in bot-wide", ephemeral=True
        )

    @discord.ui.button(label="Opt Out", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self.consent.opt_out(interaction.user.id):
            return await interaction.response.send_message(
                "You are already opted out.", ephemeral=True
            )
        await interaction.response.send_message(
            "You are now opted out bot-wide", ephemeral=True
        )


async def maybe_send_consent_embed(
    consent: "ConsentService", channel: discord.abc.Messageable, users: Set[discord.Member]
) -> bool:
    """Send the opt-in/out embed if warranted. Returns True when sent."""
    if not users:
        return False
    if await consent.config.guild(channel.guild).optin_disable_embed():
        return False
    # 33% chance, or always when several users still need to decide
    if not (random.random() <= 0.33 or len(users) > 3):
        return False

    users_mentions = ", ".join(user.mention for user in users)
    embed = discord.Embed(
        title=CONSENT_EMBED_TITLE,
        color=await consent.bot.get_embed_color(channel),
    )
    embed.description = (
        f"{users_mentions}\n"
        "Please choose whether to allow a subset of your Discord messages from any server with the bot, "
        "to be sent to OpenAI or an external party.\n"
        "This will allow the bot to reply to your messages or use your messages.\n"
        "This message will disappear if all current chatters have made a choice."
    )
    await channel.send(embed=embed, view=ConsentView(consent))
    return True
