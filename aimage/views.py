import asyncio
import io
from collections import OrderedDict

import discord
from redbot.core.bot import Red

from aimage.abc import MixinMeta
from aimage.constants import (PARAM_GROUP_REGEX, PARAM_REGEX, PARAMS_BLACKLIST,
                              VIEW_TIMEOUT)
from aimage.functions import delete_button_after


class ImageActions(discord.ui.View):
    def __init__(self, cog: MixinMeta, image_info: str, payload: dict, author: discord.Member, channel: discord.TextChannel):
        self.info_string = image_info
        self.payload = payload
        self.bot: Red = cog.bot
        self.generate_image = cog.generate_image
        self.og_user = author
        self.channel = channel
        super().__init__(timeout=VIEW_TIMEOUT)

    @discord.ui.button(emoji='🔎')
    async def get_caption(self, interaction: discord.Interaction, _: discord.ui.Button):
        if "Steps: " in self.info_string:
            embed = await self.get_params_embed()
            view = ParamsView(self.info_string, interaction)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            msg = await interaction.original_response()
            asyncio.create_task(delete_button_after(msg))
        else:
            await interaction.response.send_message(f'Parameters for this image:\n```yaml\n{self.info_string}```')

    @discord.ui.button(emoji='🔄')
    async def regenerate_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.payload["seed"] = -1
        prompt = self.payload["prompt"]
        button.disabled = True
        await interaction.message.edit(view=self)
        await self.generate_image(interaction, prompt, payload=self.payload)
        button.disabled = False
        await interaction.message.edit(view=self)

    @discord.ui.button(emoji='🗑️')
    async def delete_image(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not (await self._check_if_can_delete(interaction)):
            return await interaction.response.send_message(content=":warning: Only the requester and staff can delete this image!", ephemeral=True)

        button.disabled = True
        await interaction.message.delete()

        prompt = self.payload["prompt"]
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

    async def get_params_embed(self) -> discord.Embed:
        output_dict = OrderedDict()
        prompts, params = self.info_string.rsplit("Steps: ", 1)
        try:
            output_dict["Prompt"], output_dict["Negative Prompt"] = prompts.rsplit("Negative prompt: ", 1)
        except:
            output_dict["Prompt"] = prompts
        params = f"Steps: {params},"
        params = PARAM_GROUP_REGEX.sub("", params)
        param_list = PARAM_REGEX.findall(params)
        for key, value in param_list:
            if len(output_dict) > 24 or any(blacklisted in key for blacklisted in PARAMS_BLACKLIST):
                continue
            output_dict[key] = value
        for key in output_dict:
            if len(output_dict[key]) > 1000:
                output_dict[key] = output_dict[key][:1000] + "..."

        embed = discord.Embed(title="Image Parameters", color=await self.bot.get_embed_color(self.channel))
        for key, value in output_dict.items():
            embed.add_field(name=key, value=value, inline='Prompt' not in key)
        return embed


class ParamsView(discord.ui.View):
    def __init__(self, params: str, interaction: discord.Interaction):
        super().__init__()
        self.params = params
        self.src_interaction = interaction

    @discord.ui.button(emoji="🔧", label='View Full', style=discord.ButtonStyle.grey)
    async def view_full_parameters(self, ctx: discord.Interaction, _: discord.Button):
        if len(self.params) < 1980:
            await ctx.response.send_message(f"```yaml\n{self.params}```", ephemeral=True)
        else:
            with io.StringIO() as f:
                f.write(self.params)
                f.seek(0)
                await ctx.response.send_message(file=discord.File(f, "parameters.yaml"), ephemeral=True)

        self.stop()
        await self.src_interaction.edit_original_response(view=None)
