import discord
from redbot.core import Config


class OptView(discord.ui.View):
    def __init__(self, config: Config):
        self.config = config
        super().__init__()

    @discord.ui.button(label='Opt In', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        optin = await self.config.optin()
        if interaction.user.id in await self.config.optin():
            return await interaction.response.send_message("You are already opted in.", ephemeral=True)
        optout = await self.config.optout()
        if interaction.user.id in optout:
            optout.remove(interaction.user.id)
            await self.config.optout.set(optout)
        optin.append(interaction.user.id)
        await self.config.optin.set(optin)
        await interaction.response.send_message("You are now opted in bot-wide", ephemeral=True)

    @discord.ui.button(label='Opt Out', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        optout = await self.config.optout()
        if interaction.user.id in optout:
            return await interaction.response.send_message("You are already opted out.", ephemeral=True)
        optin = await self.config.optin()
        if interaction.user.id in optin:
            optin.remove(interaction.user.id)
            await self.config.optin.set(optin)
        optout.append(interaction.user.id)
        await self.config.optout.set(optout)
        await interaction.response.send_message("You are now opted out bot-wide", ephemeral=True)