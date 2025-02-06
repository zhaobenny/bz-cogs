import asyncio
import io
import logging
import random
from typing import Union

import aiohttp
import discord
from redbot.core import commands

from aimage.abc import MixinMeta
from aimage.apis.a1111 import A1111
from aimage.apis.response import ImageResponse
from aimage.common.helpers import delete_button_after, send_response
from aimage.common.params import ImageGenParams
from aimage.views.image_actions import ImageActions

logger = logging.getLogger("red.bz_cogs.aimage")


class ImageHandler(MixinMeta):
    async def _execute_image_generation(self, context: Union[commands.Context, discord.Interaction],
                                        payload: dict = None,
                                        params: ImageGenParams = None,
                                        generate_method: str = 'generate_image'):

        if not isinstance(context, discord.Interaction):
            await context.message.add_reaction("⏳")

        guild = context.guild
        user = context.user if isinstance(context, discord.Interaction) else context.author

        if self.generating[user.id]:
            content = ":warning: You must wait for your current image to finish generating before you can request a new one."
            return await send_response(context, content=content, ephemeral=True)

        prompt = params.prompt if params else payload.get("prompt", "")

        if await self._contains_blacklisted_word(guild, prompt):
            return await send_response(context, content=":warning: Prompt contains blacklisted words!")

        try:
            self.generating[user.id] = True
            api = await self.get_api_instance(context)
            generate_func = getattr(api, generate_method)
            response: ImageResponse = await generate_func(params, payload)
        except ValueError as error:
            return await send_response(context, content=f":warning: Invalid parameter: {error}", ephemeral=True)
        except aiohttp.ClientResponseError as error:
            logger.exception(f"Failed request in host {guild.id}")
            return await send_response(context, content=":warning: Timed out! Bad response from host!", ephemeral=True)
        except aiohttp.ClientConnectorError:
            logger.exception(f"Failed request in server {guild.id}")
            return await send_response(context, content=":warning: Timed out! Could not reach host!", ephemeral=True)
        except NotImplementedError:
            return await send_response(context, content=":warning: This method is not supported by the host!", ephemeral=True)
        except Exception:
            logger.exception(f"Failed request in server {guild.id}")
            return await send_response(context, content=":warning: Something went wrong!", ephemeral=True)
        finally:
            self.generating[user.id] = False

        if response.is_nsfw and not await self.config.guild(guild).allow_nsfw():
            return await send_response(context, content=f"🔞 {user.mention} generated a possible NSFW image with prompt: `{prompt}`", allowed_mentions=discord.AllowedMentions.none())

        file = discord.File(io.BytesIO(response.data), filename=f"image.{response.extension}")
        view = ImageActions(self, response.info_string, response.payload, user, context.channel)
        msg = await send_response(context, file=file, view=view)
        asyncio.create_task(delete_button_after(msg))

        if (random.random() > 0.51):  # update only half the time
            asyncio.create_task(self._update_autocomplete_cache(context))

        imagescanner = self.bot.get_cog("ImageScanner")
        if imagescanner and response.extension == "png":
            if context.channel.id in imagescanner.scan_channels:
                imagescanner.image_cache[msg.id] = ({1: response.info_string}, {1: response.data})
                await msg.add_reaction("🔎")

    async def generate_image(self, context: Union[commands.Context, discord.Interaction],
                             payload: dict = None,
                             params: ImageGenParams = None):
        await self._execute_image_generation(context, payload, params, 'generate_image')

    async def generate_img2img(self, context: discord.Interaction,
                               payload: dict = None,
                               params: ImageGenParams = None):
        await self._execute_image_generation(context, payload, params, 'generate_img2img')

    async def _contains_blacklisted_word(self, guild: discord.Guild, prompt: str):
        blacklist = await self.config.guild(guild).words_blacklist()
        return any(word in prompt.lower() for word in blacklist)
