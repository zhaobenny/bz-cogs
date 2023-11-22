import discord
from redbot.core.bot import Red


class ImageActions(discord.ui.View):
    def __init__(self, payload, bot: Red, author: discord.Member):
        self.payload = payload
        self.bot = bot
        self.og_user = author
        super().__init__(timeout=60)

    @discord.ui.button(emoji='🔎')
    async def get_caption(self, interaction: discord.Interaction, button: discord.ui.Button):
        prompt = self.payload["prompt"]
        await interaction.response.send_message(f'The prompt used to generate the image was: `{prompt}`')

    @discord.ui.button(emoji='🗑️')
    async def delete_image(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not (await self._check_if_can_delete(interaction)):
            return await interaction.response.send_message(content=":warning: Only the requester and staff can delete this image!", ephemeral=True)

        await interaction.message.delete()
        prompt = self.payload["prompt"]
        await interaction.response.send_message(f'{interaction.user.mention} deleted a image with prompt `{prompt}` requested by {self.og_user.mention}', allowed_mentions=discord.AllowedMentions.none())
        self.stop()

    async def _check_if_can_delete(self, interaction: discord.Interaction):
        is_og_user = interaction.user.id == self.og_user.id

        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        is_staff = await self.bot.is_mod(member) or await self.bot.is_admin(member) or await self.bot.is_owner(member)

        return is_og_user or is_staff
