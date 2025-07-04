import io
import discord
from redbot.core.i18n import Translator
from discord.errors import NotFound, Forbidden, HTTPException

_ = Translator("AImage", __file__)


class ParamsView(discord.ui.View):
    def __init__(self, params: str, interaction: discord.Interaction):
        super().__init__()
        self.params = params
        self.src_interaction = interaction

    @discord.ui.button(emoji="🔧", label=_("View Full"))
    async def view_full_parameters(
        self, interaction: discord.Interaction, _: discord.Button
    ):
        if len(self.params) < 1980:
            await interaction.response.send_message(
                _("```yaml\n{params}```").format(params=self.params), ephemeral=True
            )
        else:
            with io.StringIO() as f:
                f.write(self.params)
                f.seek(0)
                await interaction.response.send_message(
                    file=discord.File(f, "parameters.yaml"), ephemeral=True
                )

        self.stop()
        try:
            await self.src_interaction.edit_original_response(view=None)
        except (NotFound, Forbidden, HTTPException):
            pass
