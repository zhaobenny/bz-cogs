from __future__ import annotations

from typing import Optional

import discord
from redbot.core import checks, commands

from aiuser.config.defaults import DEFAULT_STT_PROVIDER
from aiuser.settings._groups import aiuser
from aiuser.settings.functions.utilities import provider_key_error
from aiuser.speech.stt import DEFAULT_MODELS, PROVIDERS
from aiuser.types.abc import MixinMeta


class AudioScanSettings(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def audioscan(self, _):
        """Change the audio transcription setting"""
        pass

    @audioscan.command(name="toggle")
    async def audio_scanning(self, ctx: commands.Context):
        """Toggle audio transcription"""
        guild_conf = self.config.guild(ctx.guild)
        value = not (await guild_conf.scan_audio())
        provider = (
            await guild_conf.scan_audio_provider() or DEFAULT_STT_PROVIDER
        ).lower()

        if value:
            key_error = await provider_key_error(self.bot, ctx, provider)
            if key_error:
                return await ctx.send(key_error)

        await guild_conf.scan_audio.set(value)
        embed = discord.Embed(
            title="Transcribing Audio for this server now set to:",
            description=f"`{value}`",
            color=await ctx.embed_color(),
        )
        if value:
            embed.add_field(
                name="👁️ __PRIVACY WARNING__",
                value=(
                    "This will send audio attachments to the configured "
                    "speech-to-text provider for processing!"
                ),
                inline=False,
            )
        return await ctx.send(embed=embed)

    @audioscan.command(name="provider")
    async def audio_provider(self, ctx: commands.Context, provider: str):
        """Set the speech-to-text provider."""
        provider = provider.strip().lower()
        if provider not in PROVIDERS:
            return await ctx.send(
                "Available audio transcription providers: "
                + ", ".join(f"`{p}`" for p in PROVIDERS)
            )

        key_error = await provider_key_error(self.bot, ctx, provider)
        if key_error:
            return await ctx.send(key_error)

        guild_conf = self.config.guild(ctx.guild)
        previous_provider = await guild_conf.scan_audio_provider()
        previous_provider = previous_provider.strip().lower()
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
            title="Audio transcription provider now set to:",
            description=f"`{provider}`",
            color=await ctx.embed_color(),
        )
        if restored:
            embed.add_field(
                name="🔄 Restored",
                value="Restored previously set model for this provider.",
                inline=False,
            )
        embed.add_field(
            name="Model",
            value=f"`{model or DEFAULT_MODELS.get(provider)}`",
            inline=True,
        )
        await ctx.send(embed=embed)

    @audioscan.command(name="model")
    async def audio_model(self, ctx: commands.Context, *, model: Optional[str] = None):
        """Set the speech-to-text model, or blank to reset to the default."""
        model = model.strip() if model else None
        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.scan_audio_model.set(model)
        provider = (
            await guild_conf.scan_audio_provider() or DEFAULT_STT_PROVIDER
        ).lower()

        embed = discord.Embed(
            title="Audio transcription model now set to:",
            description=f"`{model or DEFAULT_MODELS.get(provider)}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @audioscan.command(name="maxduration")
    async def audio_maxduration(self, ctx: commands.Context, seconds: int):
        """Set max audio duration in seconds. Longer audio is trimmed with ffmpeg when possible."""
        if seconds < 1:
            return await ctx.send("⚠️ Duration must be at least 1 second.")

        await self.config.guild(ctx.guild).max_audio_duration.set(seconds)
        embed = discord.Embed(
            title="Max audio duration to transcribe now set to:",
            description=f"`{seconds}` seconds",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)
