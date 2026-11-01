import asyncio

import discord


class CallbackModal(discord.ui.Modal, title="Finish ChatGPT sign-in"):
    callback_url = discord.ui.TextInput(
        label="Full callback URL",
        max_length=4000,
        placeholder="http://127.0.0.1:1455/auth/callback?...",
    )

    def __init__(self, view):
        super().__init__(timeout=300)
        self.login = view

    async def on_submit(self, interaction):
        if (
            interaction.user.id != self.login.owner_id
            or not await self.login.bot.is_owner(interaction.user)
        ):
            return await interaction.response.send_message(
                "This sign-in belongs to another owner.", ephemeral=True
            )
        if self.login.result.done():
            return await interaction.response.send_message(
                "This sign-in has expired.", ephemeral=True
            )
        await interaction.response.send_message(
            "Checking your sign-in...", ephemeral=True
        )
        self.login.result.set_result((self.callback_url.value, interaction))
        self.login.stop()

    async def on_error(self, interaction, error):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Sign-in failed. Start again.", ephemeral=True
            )


class ChatGPTLoginView(discord.ui.View):
    def __init__(self, bot, owner_id):
        super().__init__(timeout=300)
        self.bot, self.owner_id = bot, owner_id
        self.result = asyncio.get_running_loop().create_future()

    async def interaction_check(self, interaction):
        if interaction.user.id == self.owner_id and await self.bot.is_owner(
            interaction.user
        ):
            return True
        await interaction.response.send_message(
            "Only the owner who started sign-in can use this.", ephemeral=True
        )
        return False

    @discord.ui.button(label="Paste callback URL", style=discord.ButtonStyle.primary)
    async def paste(self, interaction, button):
        await interaction.response.send_modal(CallbackModal(self))

    async def on_timeout(self):
        if not self.result.done():
            self.result.cancel()
