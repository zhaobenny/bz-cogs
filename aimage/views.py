import discord
from redbot.core.bot import Red


class ImageActions(discord.ui.View):
    def __init__(self, image_info: str, bot: Red, author: discord.Member):
        self.info_string = image_info
        self.bot = bot
        self.og_user = author
        super().__init__()

    @discord.ui.button(emoji='🔎')
    async def get_caption(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f'Parameters for this image were:\n```\n{self.info_string}```')
        button.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(emoji='🗑️')
    async def delete_image(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not (await self._check_if_can_delete(interaction)):
            return await interaction.response.send_message(content=":warning: Only the requester and staff can delete this image!", ephemeral=True)

        button.disabled = True
        await interaction.message.delete()

        prompt = self.info_string.split("\n")[0]  # jank

        if interaction.user.id == self.og_user.id:
            await interaction.response.send_message(f'{self.og_user.mention} deleted their requested image with prompt: `{prompt}`', allowed_mentions=discord.AllowedMentions.none())
        else:
            await interaction.response.send_message(f'{interaction.user.mention} deleted a image requested by {self.og_user.mention} with prompt: `{prompt}`', allowed_mentions=discord.AllowedMentions.none())

        self.stop()

    async def _check_if_can_delete(self, interaction: discord.Interaction):
        is_og_user = interaction.user.id == self.og_user.id

        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        is_staff = await self.bot.is_mod(member) or await self.bot.is_admin(member) or await self.bot.is_owner(member)

        return is_og_user or is_staff
