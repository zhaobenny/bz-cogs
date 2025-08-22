import asyncio
import io
from collections import OrderedDict
from copy import copy
from typing import Optional

import discord
from redbot.core.bot import Red

from aimage.abc import MixinMeta
from aimage.common.constants import (ADETAILER_ARGS, AUTO_COMPLETE_UPSCALERS,
                                     PARAM_GROUP_REGEX, PARAM_REGEX,
                                     PARAMS_BLACKLIST, VIEW_TIMEOUT)
from aimage.common.helpers import delete_button_after
from aimage.views.params import ParamsView


class ImageActions(discord.ui.View):
    def __init__(self, cog: MixinMeta, image_info: str, payload: dict, author: discord.Member, channel: discord.TextChannel, maxsize: int):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.info_string = image_info
        self.payload = payload
        self.bot: Red = cog.bot
        self.config = cog.config
        self.cache = cog.autocomplete_cache
        self.og_user = author
        self.channel = channel
        self.maxsize = maxsize
        self.generate_image = cog.generate_image
        self.generate_img2img = cog.generate_img2img

        self.button_caption = discord.ui.Button(emoji='🔎')
        self.button_caption.callback = self.get_caption
        self.button_regenerate = discord.ui.Button(emoji='🔄')
        self.button_regenerate.callback = self.regenerate_image
        self.button_variation = discord.ui.Button(emoji='🤏🏻')
        self.button_variation.callback = self.variation_image
        self.button_upscale = discord.ui.Button(emoji='⬆')
        self.button_upscale.callback = self.upscale_image
        self.button_delete = discord.ui.Button(emoji='🗑️')
        self.button_delete.callback = self.delete_image

        self.add_item(self.button_caption)
        if not payload.get("enable_hr", False):
            self.add_item(self.button_regenerate)
            self.add_item(self.button_variation)
            if not payload.get("init_images", []) and "AI Horde" not in self.info_string:
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
        await interaction.response.defer(thinking=True)
        self.payload["seed"] = -1
        self.payload["subseed"] = -1
        self.payload["subseed_strength"] = 0
        self.button_regenerate.disabled = True
        await interaction.message.edit(view=self)
        if self.payload.get("init_images", []):
            await self.generate_img2img(interaction, payload=self.payload)
        else:
            await self.generate_image(interaction, payload=self.payload)
        self.button_regenerate.disabled = False
        if not self.is_finished():
            try:
                await interaction.message.edit(view=self)
            except:
                pass

    async def variation_image(self, interaction: discord.Interaction):
        from aimage.views.variation import VariationView
        view = VariationView(self, interaction)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def upscale_image(self, interaction: discord.Interaction):
        from aimage.views.hi_res import HiresView
        view = HiresView(self, interaction, self.maxsize)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def delete_image(self, interaction: discord.Interaction):
        if not (await self._check_if_can_delete(interaction)):
            return await interaction.response.send_message(content=":warning: Only the requester and members with `Manage Messages` permission can delete this image!", ephemeral=True)

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
        can_delete = await self.bot.is_owner(member) or interaction.channel.permissions_for(member).manage_messages

        return is_og_user or can_delete
