import discord


class ImageActions(discord.ui.View):
    def __init__(self, payload):
        self.payload = payload
        super().__init__(timeout=60)

    @discord.ui.button(emoji='🔎')
    async def get_caption(self, interaction: discord.Interaction, button: discord.ui.Button):
        prompt = self.payload["prompt"]
        await interaction.response.send_message(f'The prompt used to generate the image was: `{prompt}`')

    @discord.ui.button(emoji='🗑️')
    async def delete_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        prompt = self.payload["prompt"]
        await interaction.response.send_message(f'User {interaction.user.mention} deleted a image with prompt `{prompt}`', allowed_mentions=discord.AllowedMentions.none())
        self.stop()
