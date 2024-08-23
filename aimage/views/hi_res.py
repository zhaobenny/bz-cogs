from copy import copy

import discord

from aimage.common.constants import ADETAILER_ARGS, AUTO_COMPLETE_UPSCALERS
from aimage.views.image_actions import ImageActions


class HiresView(discord.ui.View):
    def __init__(self, parent: ImageActions, interaction: discord.Interaction, maxsize: int):
        super().__init__()
        self.src_view = parent
        self.src_interaction = interaction
        self.src_button = parent.button_upscale
        self.payload = copy(parent.payload)
        self.generate_image = parent.generate_image
        upscalers = AUTO_COMPLETE_UPSCALERS + parent.cache[interaction.guild.id].get("upscalers", [])
        maxscale = ((maxsize*maxsize) / (self.payload["width"]*self.payload["height"]))**0.5
        scales = [num/100 for num in range(100, min(max(int(maxscale * 100) + 1, 101), 201), 25)]
        self.upscaler = upscalers[0]
        self.scale = scales[-1]
        self.denoising = 0.5
        self.adetailer = "adetailer" in parent.cache[interaction.guild.id].get("scripts", [])
        self.add_item(UpscalerSelect(self, upscalers))
        self.add_item(ScaleSelect(self, scales))
        self.add_item(DenoisingSelect(self))
        if self.adetailer:
            self.add_item(AdetailerSelect(self))

    @discord.ui.button(emoji='⬆', label='Upscale', style=discord.ButtonStyle.blurple, row=4)
    async def upscale(self, interaction: discord.Interaction, _: discord.Button):
        await interaction.response.defer(thinking=True)
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
        if self.adetailer:
            self.payload["alwayson_scripts"].update(ADETAILER_ARGS)
        elif "ADetailer" in self.payload["alwayson_scripts"]:
            del self.payload["alwayson_scripts"]["ADetailer"]

        self.src_button.disabled = True
        await self.src_interaction.message.edit(view=self.src_view)
        await self.src_interaction.delete_original_response()
        await self.generate_image(interaction, payload=self.payload)

        self.src_button.disabled = False
        if not self.src_view.is_finished():
            try:
                await self.src_interaction.message.edit(view=self.src_view)
            except:
                pass


class UpscalerSelect(discord.ui.Select):
    def __init__(self, parent: HiresView, upscalers: list):
        self.parent = parent
        options = [discord.SelectOption(label=name, default=i == 1) for i, name in enumerate(upscalers[:25])]
        super().__init__(options=options)

    async def callback(self, interaction: discord.Interaction):
        self.parent.upscaler = self.values[0]
        for option in self.options:
            option.default = option.value == self.values[0]
        await interaction.response.edit_message(view=self.parent)


class ScaleSelect(discord.ui.Select):
    def __init__(self, parent: HiresView, scales: list):
        self.parent = parent
        options = [discord.SelectOption(label=f"x{num:.2f}", value=str(num)) for num in scales]
        options[-1].default = True
        super().__init__(options=options)

    async def callback(self, interaction: discord.Interaction):
        self.parent.scale = float(self.values[0])
        for option in self.options:
            option.default = option.value == self.values[0]
        await interaction.response.edit_message(view=self.parent)


class DenoisingSelect(discord.ui.Select):
    def __init__(self, parent: HiresView):
        self.parent = parent
        options = [discord.SelectOption(label=f"Denoising: {num / 100:.2f}", value=str(num / 100), default=num == 55)
                   for num in range(0, 100, 5)]
        super().__init__(options=options)

    async def callback(self, interaction: discord.Interaction):
        self.parent.denoising = float(self.values[0])
        for option in self.options:
            option.default = option.value == self.values[0]
        await interaction.response.edit_message(view=self.parent)


class AdetailerSelect(discord.ui.Select):
    def __init__(self, parent: HiresView):
        self.parent = parent
        super().__init__(options=[
            discord.SelectOption(label="ADetailer Enabled", value=str(1), default=True),
            discord.SelectOption(label="ADetailer Disabled", value=str(0)),
        ])

    async def callback(self, interaction: discord.Interaction):
        self.parent.adetailer = bool(int(self.values[0]))
        for option in self.options:
            option.default = option.value == self.values[0]
        await interaction.response.edit_message(view=self.parent)
