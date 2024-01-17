import asyncio
import io
from collections import OrderedDict, defaultdict

import discord
from redbot.core.bot import Red
from typing import Optional, Coroutine

from aimage.abc import MixinMeta
from aimage.constants import (PARAM_GROUP_REGEX, PARAM_REGEX, PARAMS_BLACKLIST,
                              VIEW_TIMEOUT, AUTO_COMPLETE_UPSCALERS)
from aimage.functions import delete_button_after


class ImageActions(discord.ui.View):
    def __init__(self, cog: MixinMeta, image_info: str, payload: dict, author: discord.Member, channel: discord.TextChannel):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.info_string = image_info
        self.payload = payload
        self.bot: Red = cog.bot
        self.generate_image = cog.generate_image
        self.cache = cog.autocomplete_cache
        self.og_user = author
        self.channel = channel

        self.button_caption = discord.ui.Button(emoji='🔎')
        self.button_caption.callback = self.get_caption
        self.button_regenerate = discord.ui.Button(emoji='🔄')
        self.button_regenerate.callback = self.regenerate_image
        self.button_upscale = discord.ui.Button(emoji='⬆')
        self.button_upscale.callback = self.upscale_image
        self.button_delete = discord.ui.Button(emoji='🗑️')
        self.button_delete.callback = self.delete_image

        self.add_item(self.button_caption)
        if not payload.get("enable_hr", False):
            self.add_item(self.button_regenerate)
            if payload["width"]*payload["height"] <= 768*768:
                self.add_item(self.button_upscale)
        self.add_item(self.button_delete)

    async def get_caption(self, interaction: discord.Interaction):
        embed = await self._get_params_embed()
        if embed:
            view = ParamsView(self.info_string, interaction)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            msg = await interaction.original_response()
            asyncio.create_task(delete_button_after(msg))
        else:
            await interaction.response.send_message(f'Parameters for this image:\n```yaml\n{self.info_string}```')

    async def regenerate_image(self, interaction: discord.Interaction):
        params = self.get_params_dict()
        if params and float(params.get("Variation seed strength", 0)) > 0:
            self.payload["seed"] = int(params["Seed"])
            self.payload["subseed"] = -1
        else:
            self.payload["seed"] = -1
        self.button_regenerate.disabled = True
        await interaction.message.edit(view=self)
        await self.generate_image(interaction, payload=self.payload)
        self.button_regenerate.disabled = False
        if not self.is_finished():
            try:
                await interaction.message.edit(view=self)
            except:
                pass

    async def upscale_image(self, interaction: discord.Interaction):
        view = HiresView(self, self.button_upscale, interaction, self.payload, self.cache, self.generate_image)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def delete_image(self, interaction: discord.Interaction):
        if not (await self._check_if_can_delete(interaction)):
            return await interaction.response.send_message(content=":warning: Only the requester and staff can delete this image!", ephemeral=True)

        self.button_delete.disabled = True
        await interaction.message.delete()

        prompt = self.payload["prompt"]
        if interaction.user.id == self.og_user.id:
            await interaction.response.send_message(f'{self.og_user.mention} deleted their requested image with prompt: `{prompt}`', allowed_mentions=discord.AllowedMentions.none())
        else:
            await interaction.response.send_message(f'{interaction.user.mention} deleted a image requested by {self.og_user.mention} with prompt: `{prompt}`', allowed_mentions=discord.AllowedMentions.none())

        self.stop()

    def get_params_dict(self) -> Optional[dict]:
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
        params = self.get_params_dict()
        if not params:
            return None
        embed = discord.Embed(title="Image Parameters", color=await self.bot.get_embed_color(self.channel))
        for key, value in params.items():
            embed.add_field(name=key, value=value, inline="Prompt" not in key)
        return embed

    async def _check_if_can_delete(self, interaction: discord.Interaction):
        is_og_user = interaction.user.id == self.og_user.id

        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        is_staff = await self.bot.is_mod(member) or await self.bot.is_admin(member) or await self.bot.is_owner(member)

        return is_og_user or is_staff


class ParamsView(discord.ui.View):
    def __init__(self, params: str, interaction: discord.Interaction):
        super().__init__()
        self.params = params
        self.src_interaction = interaction

    @discord.ui.button(emoji='🔧', label='View Full')
    async def view_full_parameters(self, interaction: discord.Interaction, _: discord.Button):
        if len(self.params) < 1980:
            await interaction.response.send_message(f"```yaml\n{self.params}```", ephemeral=True)
        else:
            with io.StringIO() as f:
                f.write(self.params)
                f.seek(0)
                await interaction.response.send_message(file=discord.File(f, "parameters.yaml"), ephemeral=True)

        self.stop()
        try:
            await self.src_interaction.edit_original_response(view=None)
        except:
            pass


class HiresView(discord.ui.View):
    def __init__(self,
                 parent: ImageActions,
                 button: discord.ui.Button,
                 interaction: discord.Interaction,
                 payload: dict,
                 cache: defaultdict,
                 generate_image):
        super().__init__()
        self.src_view = parent
        self.src_button = button
        self.src_interaction = interaction
        self.payload = payload
        self.generate_image = generate_image
        upscalers = (AUTO_COMPLETE_UPSCALERS + cache[interaction.guild.id]["upscalers"])[:25]
        self.upscaler = upscalers[0]
        self.scale = 1.5
        self.denoising = 0.5
        self.add_item(UpscalerSelect(self, upscalers))
        self.add_item(ScaleSelect(self))
        self.add_item(DenoisingSelect(self))

    @discord.ui.button(emoji='⬆', label='Upscale', style=discord.ButtonStyle.blurple, row=3)
    async def upscale(self, interaction: discord.Interaction, button: discord.Button):
        self.payload["enable_hr"] = True
        self.payload["hr_upscaler"] = self.upscaler
        self.payload["hr_scale"] = self.scale
        self.payload["denoising_strength"] = self.denoising
        self.payload["hr_second_pass_steps"] = self.payload["steps"] // 2
        self.payload["hr_prompt"] = self.payload["prompt"]
        self.payload["hr_negative_prompt"] = self.payload["negative_prompt"]
        self.payload["hr_resize_x"] = 0
        self.payload["hr_resize_y"] = 0
        params = self.src_view.get_params_dict()
        self.payload["seed"] = int(params["Seed"])
        self.payload["subseed"] = int(params.get("Variation seed", -1))

        button.disabled = True
        self.src_button.disabled = True
        await self.src_interaction.message.edit(view=self.src_view)
        await self.src_interaction.edit_original_response(view=self)
        await self.generate_image(interaction, payload=self.payload)


class UpscalerSelect(discord.ui.Select):
    def __init__(self, parent: HiresView, upscalers: list[str]):
        self.parent = parent
        super().__init__(
            options=[discord.SelectOption(label=name, default=i == 1)
                     for i, name in enumerate(upscalers)]
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent.upscaler = self.values[0]
        for option in self.options:
            option.default = option.value == self.values[0]
        await interaction.response.edit_message(view=self.parent)


class ScaleSelect(discord.ui.Select):
    def __init__(self, parent: HiresView):
        self.parent = parent
        super().__init__(
            options=[discord.SelectOption(label=f"x{num:.2f}", value=str(num), default=num == 1.5)
                     for num in (1.25, 1.5, 1.75, 2)]
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent.scale = float(self.values[0])
        for option in self.options:
            option.default = option.value == self.values[0]
        await interaction.response.edit_message(view=self.parent)


class DenoisingSelect(discord.ui.Select):
    def __init__(self, parent: HiresView):
        self.parent = parent
        super().__init__(
            options=[discord.SelectOption(label=f"Denoising: {num/100}", value=str(num/100), default=num == 50)
                     for num in range(5, 100, 5)]
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent.denoising = float(self.values[0])
        for option in self.options:
            option.default = option.value == self.values[0]
        await interaction.response.edit_message(view=self.parent)
