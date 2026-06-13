from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from aiuser.consent.service import ConsentService


class ConsentView(discord.ui.View):
    def __init__(self, consent: "ConsentService"):
        super().__init__()
        self.consent = consent

    @discord.ui.button(label="Opt In", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ):
        if not await self.consent.opt_in(interaction.user.id):
            return await interaction.response.send_message(
                "You are already opted in.", ephemeral=True
            )
        await interaction.response.send_message(
            "You are now opted in bot-wide", ephemeral=True
        )

    @discord.ui.button(label="Opt Out", style=discord.ButtonStyle.grey)
    async def cancel(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ):
        if not await self.consent.opt_out(interaction.user.id):
            return await interaction.response.send_message(
                "You are already opted out.", ephemeral=True
            )
        await interaction.response.send_message(
            "You are now opted out bot-wide", ephemeral=True
        )
