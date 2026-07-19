from __future__ import annotations

import discord
from redbot.core import checks, commands

from aiuser.config.defaults import DEFAULT_STT_PROVIDER
from aiuser.config.model_info import get_model_info
from aiuser.llm.registry import list_llm_models
from aiuser.settings._groups import aiuser
from aiuser.settings.functions.utilities import provider_key_error
from aiuser.speech.stt import DEFAULT_MODELS, PROVIDERS
from aiuser.types.abc import MixinMeta


class MediaSettings(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def media(self, _):
        """Configure image and audio inputs"""
        pass

    @media.command(name="show")
    async def media_show(self, ctx: commands.Context):
        """Show whether image and audio processing are enabled"""
        guild_conf = self.config.guild(ctx.guild)
        embed = discord.Embed(title="Media settings", color=await ctx.embed_color())
        embed.add_field(
            name="Images",
            value="Enabled" if await guild_conf.scan_images() else "Disabled",
        )
        embed.add_field(
            name="Audio",
            value="Enabled" if await guild_conf.scan_audio() else "Disabled",
        )
        return await ctx.send(embed=embed)

    @media.group(name="images", aliases=["image"])
    async def media_images(self, _):
        """Configure image processing"""
        pass

    @media_images.command(name="show")
    async def media_images_show(self, ctx: commands.Context):
        """Show image processing settings"""
        guild_conf = self.config.guild(ctx.guild)
        enabled = await guild_conf.scan_images()
        model = await guild_conf.scan_images_model()
        embed = discord.Embed(
            title="Image processing settings", color=await ctx.embed_color()
        )
        embed.add_field(
            name="Enabled",
            value="Yes" if enabled else "No",
        )
        if not enabled:
            return await ctx.send(embed=embed)
        embed.add_field(
            name="Maximum Size",
            value=f"`{await guild_conf.max_image_size() / 1024 / 1024:.2f}` MB",
        )
        embed.add_field(
            name="Detail", value=f"`{await guild_conf.scan_images_detail()}`"
        )
        embed.add_field(name="Model", value=f"`{model or 'Chat model'}`")
        return await ctx.send(embed=embed)

    @media_images.command(name="enable")
    async def media_images_enable(self, ctx: commands.Context):
        """Allow attached images to be sent to the configured model"""
        await self.config.guild(ctx.guild).scan_images.set(True)
        embed = discord.Embed(
            title="Image processing is now enabled",
            description="Image attachments may be sent to the configured endpoint.",
            color=await ctx.embed_color(),
        )
        scan_model = await self.config.guild(ctx.guild).scan_images_model()
        model = scan_model or await self.config.guild(ctx.guild).model()
        if not get_model_info(model).supports_vision:
            embed.set_footer(text="⚠️ Ensure the selected model supports vision")
        return await ctx.send(embed=embed)

    @media_images.command(name="disable")
    async def media_images_disable(self, ctx: commands.Context):
        """Stop processing attached images"""
        await self.config.guild(ctx.guild).scan_images.set(False)
        return await ctx.send("Image processing is now disabled.")

    @media_images.group(
        name="max_size", aliases=["maxsize"], invoke_without_command=True
    )
    async def media_images_max_size(self, ctx: commands.Context):
        """Show the maximum image size"""
        size = await self.config.guild(ctx.guild).max_image_size()
        return await ctx.maybe_send_embed(
            f"Maximum image size: `{size / 1024 / 1024:.2f}` MB"
        )

    @media_images_max_size.command(name="set")
    async def media_images_max_size_set(self, ctx: commands.Context, megabytes: float):
        """Set the maximum image size in megabytes"""
        if megabytes <= 0:
            return await ctx.send("Please enter a positive size.")
        await self.config.guild(ctx.guild).max_image_size.set(megabytes * 1024 * 1024)
        return await ctx.send(f"Maximum image size set to `{megabytes:.2f}` MB.")

    @media_images.group(name="detail", invoke_without_command=True)
    async def media_images_detail(self, ctx: commands.Context):
        """Show the image input detail"""
        detail = await self.config.guild(ctx.guild).scan_images_detail()
        return await ctx.maybe_send_embed(f"Image detail: `{detail}`")

    @media_images_detail.command(name="set")
    async def media_images_detail_set(self, ctx: commands.Context, detail: str):
        """Set image detail to low, high, or auto"""
        detail = detail.lower()
        if detail not in {"low", "high", "auto"}:
            return await ctx.send("Image detail must be `low`, `high`, or `auto`.")
        await self.config.guild(ctx.guild).scan_images_detail.set(detail)
        return await ctx.send(f"Image detail set to `{detail}`.")

    @media_images.group(name="model", invoke_without_command=True)
    async def media_images_model(self, ctx: commands.Context):
        """Show the model used to process images"""
        model = await self.config.guild(ctx.guild).scan_images_model()
        return await ctx.maybe_send_embed(f"Image model: `{model or 'Chat model'}`")

    @media_images_model.command(name="list")
    async def media_images_model_list(self, ctx: commands.Context):
        """List available models that support image input"""
        models = await list_llm_models(self.services)
        models = [model for model in models if get_model_info(model).supports_vision]
        return await self._paginate_models(ctx, models)

    @media_images_model.command(name="set")
    async def media_images_model_set(self, ctx: commands.Context, *, model: str):
        """Set the model used to process images"""
        models = await list_llm_models(self.services)
        models = [name for name in models if get_model_info(name).supports_vision]
        if model not in models:
            await ctx.send("⚠️ Not a valid image model!")
            return await self._paginate_models(ctx, models, query=model)
        await self.config.guild(ctx.guild).scan_images_model.set(model)
        return await ctx.send(f"Image model set to `{model}`.")

    @media_images_model.command(name="clear")
    async def media_images_model_clear(self, ctx: commands.Context):
        """Use the main chat model to process images"""
        await self.config.guild(ctx.guild).scan_images_model.set(None)
        return await ctx.send("Image processing will now use the chat model.")

    @media.group(name="audio")
    async def media_audio(self, _):
        """Configure audio transcription"""
        pass

    @media_audio.command(name="show")
    async def media_audio_show(self, ctx: commands.Context):
        """Show audio transcription settings"""
        guild_conf = self.config.guild(ctx.guild)
        enabled = await guild_conf.scan_audio()
        provider = (
            await guild_conf.scan_audio_provider() or DEFAULT_STT_PROVIDER
        ).lower()
        model = await guild_conf.scan_audio_model() or DEFAULT_MODELS.get(provider)
        embed = discord.Embed(
            title="Audio transcription settings", color=await ctx.embed_color()
        )
        embed.add_field(name="Enabled", value="Yes" if enabled else "No")
        if not enabled:
            return await ctx.send(embed=embed)
        embed.add_field(name="Provider", value=f"`{provider}`")
        embed.add_field(name="Model", value=f"`{model}`")
        embed.add_field(
            name="Maximum Duration",
            value=f"`{await guild_conf.max_audio_duration()}` seconds",
        )
        return await ctx.send(embed=embed)

    @media_audio.command(name="enable")
    async def media_audio_enable(self, ctx: commands.Context):
        """Allow attached audio to be transcribed"""
        guild_conf = self.config.guild(ctx.guild)
        provider = (
            await guild_conf.scan_audio_provider() or DEFAULT_STT_PROVIDER
        ).lower()
        key_error = await provider_key_error(self.bot, ctx, provider)
        if key_error:
            return await ctx.send(key_error)
        await guild_conf.scan_audio.set(True)
        embed = discord.Embed(
            title="Audio transcription is now enabled",
            description="Audio attachments may be sent to the configured provider.",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @media_audio.command(name="disable")
    async def media_audio_disable(self, ctx: commands.Context):
        """Stop transcribing attached audio"""
        await self.config.guild(ctx.guild).scan_audio.set(False)
        return await ctx.send("Audio transcription is now disabled.")

    @media_audio.group(name="provider", invoke_without_command=True)
    async def media_audio_provider(self, ctx: commands.Context):
        """Show the audio transcription provider"""
        provider = await self.config.guild(ctx.guild).scan_audio_provider()
        return await ctx.maybe_send_embed(
            f"Audio provider: `{provider or DEFAULT_STT_PROVIDER}`"
        )

    @media_audio_provider.command(name="set")
    async def media_audio_provider_set(self, ctx: commands.Context, provider: str):
        """Set the audio transcription provider"""
        provider = provider.strip().lower()
        if provider not in PROVIDERS:
            return await ctx.send(
                "Available audio providers: "
                + ", ".join(f"`{name}`" for name in PROVIDERS)
            )

        key_error = await provider_key_error(self.bot, ctx, provider)
        if key_error:
            return await ctx.send(key_error)

        guild_conf = self.config.guild(ctx.guild)
        previous_provider = (
            await guild_conf.scan_audio_provider() or DEFAULT_STT_PROVIDER
        ).lower()
        model = await guild_conf.scan_audio_model()
        restored = False

        if previous_provider != provider:
            history = await guild_conf.scan_audio_provider_history()
            history[previous_provider] = model
            saved_model = history.get(provider)
            model = saved_model or DEFAULT_MODELS.get(provider)
            restored = saved_model is not None
            await guild_conf.scan_audio_provider_history.set(history)
            await guild_conf.scan_audio_model.set(model)

        await guild_conf.scan_audio_provider.set(provider)
        embed = discord.Embed(
            title="Audio provider set to:",
            description=f"`{provider}`",
            color=await ctx.embed_color(),
        )
        embed.add_field(
            name="Model", value=f"`{model or DEFAULT_MODELS.get(provider)}`"
        )
        if restored:
            embed.set_footer(
                text="Restored the model previously used with this provider"
            )
        return await ctx.send(embed=embed)

    @media_audio.group(name="model", invoke_without_command=True)
    async def media_audio_model(self, ctx: commands.Context):
        """Show the audio transcription model"""
        guild_conf = self.config.guild(ctx.guild)
        provider = (
            await guild_conf.scan_audio_provider() or DEFAULT_STT_PROVIDER
        ).lower()
        model = await guild_conf.scan_audio_model() or DEFAULT_MODELS.get(provider)
        return await ctx.maybe_send_embed(f"Audio model: `{model}`")

    @media_audio_model.command(name="set")
    async def media_audio_model_set(self, ctx: commands.Context, *, model: str):
        """Set the audio transcription model"""
        await self.config.guild(ctx.guild).scan_audio_model.set(model.strip())
        return await ctx.send(f"Audio model set to `{model.strip()}`.")

    @media_audio_model.command(name="clear")
    async def media_audio_model_clear(self, ctx: commands.Context):
        """Use the provider's default audio transcription model"""
        await self.config.guild(ctx.guild).scan_audio_model.set(None)
        return await ctx.send("Audio model reset to the provider default.")

    @media_audio.group(
        name="max_duration", aliases=["maxduration"], invoke_without_command=True
    )
    async def media_audio_max_duration(self, ctx: commands.Context):
        """Show the maximum audio duration"""
        seconds = await self.config.guild(ctx.guild).max_audio_duration()
        return await ctx.maybe_send_embed(
            f"Maximum audio duration: `{seconds}` seconds"
        )

    @media_audio_max_duration.command(name="set")
    async def media_audio_max_duration_set(self, ctx: commands.Context, seconds: int):
        """Set the maximum audio duration in seconds"""
        if seconds < 1:
            return await ctx.send("Duration must be at least one second.")
        await self.config.guild(ctx.guild).max_audio_duration.set(seconds)
        return await ctx.send(f"Maximum audio duration set to `{seconds}` seconds.")
