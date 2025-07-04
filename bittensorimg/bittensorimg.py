import base64
import io
import logging

import aiohttp
import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n

log = logging.getLogger("red.bz_cogs.bitensorimggen")
_ = Translator("BitTensorImg", __file__)

NINETEEN_API_URL = "https://api.nineteen.ai/v1/text-to-image"
CHUTES_API_URL = "https://chutes-flux-1-dev.chutes.ai/generate"
NINETEEN = "sn19"
CHUTES = "chutes"


@cog_i18n(_)
class BitTensorImg(commands.Cog):
    """Generate images using select BitTensor subnets with image generation capabilities."""

    __version__ = "2.0"
    __author__ = "zhaobenny"
    __contributor__ = "evanroby"

    def __init__(self, bot: Red):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def format_help_for_context(self, ctx):
        pre_processed = super().format_help_for_context(ctx)
        n = "\n" if "\n\n" not in pre_processed else ""
        return (
            f"{pre_processed}{n}\n"
            f"{_('Cog Version')}: {self.__version__}\n"
            f"{_('Cog Author')}: {self.__author__}\n"
            f"{_('Cog Contributor')}: {self.__contributor__}"
        )

    async def red_delete_data_for_user(self, **kwargs):
        return

    async def cog_unload(self):
        await self.session.close()

    async def _get_api_key(self, provider: str):
        """Get the API key from shared API tokens."""
        if provider == NINETEEN:
            return (await self.bot.get_shared_api_tokens(NINETEEN)).get("api_key")
        elif provider == CHUTES:
            return (await self.bot.get_shared_api_tokens(CHUTES)).get("api_key")
        return None

    async def _generate_image_nineteen(
        self,
        prompt: str,
        steps: int = 20,
        cfg_scale: float = 7.5,
        height: int = 1024,
        width: int = 1024,
        negative_prompt: str = "",
    ):
        """Generate image using sn19.ai API."""
        api_key = await self._get_api_key(NINETEEN)
        if not api_key:
            raise ValueError(_("No API key set for sn19.ai"))

        headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        data = {
            "prompt": prompt,
            "model": "flux-schnell-text-to-image",
            "steps": steps,
            "cfg_scale": cfg_scale,
            "height": height,
            "width": width,
            "negative_prompt": negative_prompt,
        }

        async with self.session.post(NINETEEN_API_URL, headers=headers, json=data) as response:
            if response.status == 200:
                res = await response.json()
                image_data = res["image_b64"]
                return base64.b64decode(image_data)
            else:
                error_text = await response.text()
                raise Exception(
                    _("sn19.ai API error: {status} - {error}").format(
                        status=response.status, error=error_text
                    )
                )

    async def _generate_image_chutes(
        self,
        prompt: str,
        steps: int = 20,
        guidance_scale: float = 7.5,
        height: int = 1024,
        width: int = 1024,
        negative_prompt: str = "",
    ):
        """Generate image using Chutes API."""
        api_key = await self._get_api_key(CHUTES)
        if not api_key:
            raise ValueError(_("No API key set for Chutes"))

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        if negative_prompt:
            log.debug(_("Chutes does not support negative prompts, ignoring"))

        data = {
            "prompt": prompt,
            "guidance_scale": guidance_scale,
            "width": width,
            "height": height,
            "num_inference_steps": steps,
        }

        async with self.session.post(CHUTES_API_URL, headers=headers, json=data) as response:
            if response.status == 200:
                return await response.read()
            else:
                error_text = await response.text()
                raise Exception(
                    _("Chutes API error: {status} - {error}").format(
                        status=response.status, error=error_text
                    )
                )

    @app_commands.command(name="bitgen")
    @app_commands.describe(
        prompt=_("The prompt to generate an image from"),
        provider=_("The image generation provider to use"),
        steps=_("Number of inference steps (1-50)"),
        guidance_scale=_("Guidance scale (1-20)"),
        height=_("Image height (256-1024)"),
        width=_("Image width (256-1024)"),
        negative_prompt=_("Things to avoid in the image"),
    )
    @app_commands.choices(
        provider=[
            app_commands.Choice(name=_("Nineteen"), value=NINETEEN),
            app_commands.Choice(name=_("Chutes"), value=CHUTES),
        ]
    )
    @commands.bot_has_permissions(attach_files=True)
    @app_commands.checks.cooldown(1, 10)
    @app_commands.guild_only()
    async def bitgen_app(
        self,
        interaction: discord.Interaction,
        prompt: str,
        provider: str = NINETEEN,
        steps: app_commands.Range[int, 1, 100] = 8,
        guidance_scale: app_commands.Range[float, 1, 10] = 3,
        height: app_commands.Range[int, 1024, 1920] = 1024,
        width: app_commands.Range[int, 1024, 1080] = 1024,
        negative_prompt: str = "",
    ):
        await interaction.response.defer(thinking=True)
        image_bytes = None
        try:
            if provider == NINETEEN:
                image_bytes = await self._generate_image_nineteen(
                    prompt, steps, guidance_scale, height, width, negative_prompt
                )
            elif provider == CHUTES:
                image_bytes = await self._generate_image_chutes(
                    prompt, steps, guidance_scale, height, width, negative_prompt
                )
            else:
                await interaction.followup.send(
                    _("Invalid provider: {provider}").format(provider=provider), ephemeral=True
                )

            file = discord.File(io.BytesIO(image_bytes), filename="image.png")
            await interaction.followup.send(file=file)
        except ValueError as e:
            await interaction.followup.send(
                _(
                    "No API key set for {provider}! Use `[p]set api {api_name} api_key,[YOUR_API_KEY_HERE]`"
                ).format(provider=provider, api_name=NINETEEN if provider == NINETEEN else CHUTES),
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"{e}")
            await interaction.followup.send(
                _("Failed to generate image using `{provider}`.\n`{error}`").format(
                    provider=provider, error=e
                ),
                ephemeral=True,
            )

    async def _handle_command(self, ctx: commands.Context, prompt: str, provider: str):
        thinking_emoji = "🤔"
        complete_emoji = "✅"
        error_emoji = "❌"
        credits_emoji = "💳"
        api_key_name = _("INVALID")
        await ctx.message.add_reaction(thinking_emoji)

        try:
            if provider == NINETEEN:
                api_key_name = NINETEEN
                image_bytes = await self._generate_image_nineteen(prompt)
            elif provider == CHUTES:
                api_key_name = CHUTES
                image_bytes = await self._generate_image_chutes(prompt)
            else:
                raise ValueError(_("Invalid provider: {provider}").format(provider=provider))

            file = discord.File(io.BytesIO(image_bytes), filename="image.png")
            await ctx.message.remove_reaction(thinking_emoji, ctx.bot.user)
            await ctx.message.add_reaction(complete_emoji)
            await ctx.send(file=file)

        except ValueError:
            await ctx.message.remove_reaction(thinking_emoji, ctx.bot.user)
            await ctx.message.add_reaction(error_emoji)
            await ctx.send(
                _(
                    "No API key set for `{provider}`! Use `[p]set api {api_name} api_key,[YOUR_API_KEY_HERE]`"
                ).format(provider=provider, api_name=api_key_name)
            )

        except Exception as e:
            await ctx.message.remove_reaction(thinking_emoji, ctx.bot.user)
            if "402" in str(e):
                await ctx.message.add_reaction(credits_emoji)
            else:
                await ctx.message.add_reaction(error_emoji)
                await ctx.send(
                    _("Failed to generate image using `{provider}`.\n`{error}`").format(
                        provider=provider, error=e
                    )
                )
            log.error(f"{e}")

    @commands.command(name="19gen")
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.bot_has_permissions(attach_files=True, add_reactions=True)
    async def nineteen_gen(self, ctx: commands.Context, *, prompt: str):
        """Generate an image using Nineteen"""
        await self._handle_command(ctx, prompt, NINETEEN)

    @commands.command(name="chutesgen")
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.bot_has_permissions(attach_files=True, add_reactions=True)
    async def chutes_gen(self, ctx: commands.Context, *, prompt: str):
        """Generate an image using Chutes"""
        await self._handle_command(ctx, prompt, CHUTES)
