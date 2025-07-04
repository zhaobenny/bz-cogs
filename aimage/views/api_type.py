import discord
from discord.ui import Select, View
from redbot.core import Config, commands
from redbot.core.i18n import Translator

from aimage.abc import MixinMeta
from aimage.common.constants import VIEW_TIMEOUT, API_Type

_ = Translator("AImage", __file__)


class APITypeSelect(Select):
    def __init__(self, config: Config, ctx: commands.Context):
        options = [
            discord.SelectOption(label=api_type.name, value=api_type.value) for api_type in API_Type
        ]
        self.ctx = ctx
        self.config = config
        super().__init__(placeholder=_("Type of API"), options=options)

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.ctx.author.id

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        await interaction.response.send_message(
            _("Selected `{value}`").format(value=selected_value), ephemeral=True
        )
        await self.config.guild(self.ctx.guild).api_type.set(selected_value)


class APITypeView(View):
    def __init__(self, cog: MixinMeta, ctx: commands.Context):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.add_item(APITypeSelect(cog.config, ctx))
