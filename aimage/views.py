import asyncio
import io
from collections import OrderedDict

import discord
from redbot.core.bot import Red
from typing import Optional

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
        embed = await self._get_params_embed()
        if embed:
            view = ParamsView(self.info_string, interaction)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            msg = await interaction.original_response()
            asyncio.create_task(delete_button_after(msg))
        else:
            await interaction.response.send_message(f'Parameters for this image:\n```yaml\n{self.info_string}```')

    @discord.ui.button(emoji='🔄')
    async def regenerate_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        params = self._get_params_dict()
        if params and float(params.get("Variation seed strength", 0)) > 0:
            self.payload["seed"] = int(params["Seed"])
            self.payload["subseed"] = -1
        else:
            self.payload["seed"] = -1
        button.disabled = True
        await interaction.message.edit(view=self)
        await self.generate_image(interaction, payload=self.payload)
        button.disabled = False
        if not self.is_finished():
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

    def _get_params_dict(self) -> Optional[dict]:
        if "Steps: " not in self.info_string:
            return None
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
        return output_dict

    async def _get_params_embed(self) -> Optional[discord.Embed]:
        params = self._get_params_dict()
        if not params:
            return None
        embed = discord.Embed(title="Image Parameters", color=await self.bot.get_embed_color(self.channel))
        for key, value in params.items():
            embed.add_field(name=key, value=value, inline="Prompt" not in key)
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
        try:
            await self.src_interaction.edit_original_response(view=None)
        except:
            pass
