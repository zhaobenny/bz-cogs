from typing import Optional

import discord
from redbot.core import commands

from aiuser.functions import names
from aiuser.speech.tts import DEFAULT_MODELS, DEFAULT_VOICES, PROVIDERS
from aiuser.settings.functions.utilities import (
    FunctionToggleHelperMixin,
    functions,
    provider_key_error,
)


class VoiceFunctionSettings(FunctionToggleHelperMixin):

    async def _save_current_voice_provider_settings(self, guild_conf, provider: str):
        history = await guild_conf.function_calling_voice_provider_history()
        history[provider] = {
            "model": await guild_conf.function_calling_voice_model(),
            "voice": await guild_conf.function_calling_voice(),
        }
        await guild_conf.function_calling_voice_provider_history.set(history)

    async def _restore_voice_provider_settings(
        self, guild_conf, provider: str
    ) -> tuple[Optional[str], Optional[str], bool]:
        history = await guild_conf.function_calling_voice_provider_history()
        saved_settings = history.get(provider)
        restored = saved_settings is not None

        if saved_settings is None:
            model = DEFAULT_MODELS.get(provider)
            voice = DEFAULT_VOICES.get(provider)
        else:
            model = saved_settings.get("model") or DEFAULT_MODELS.get(provider)
            voice = saved_settings.get("voice") or DEFAULT_VOICES.get(provider)

        await guild_conf.function_calling_voice_model.set(model)
        await guild_conf.function_calling_voice.set(voice)
        return model, voice, restored

    @functions.group(name="voice")
    async def functions_voice(self, ctx: commands.Context):
        """Voice generation function settings (per server)."""
        pass

    @functions_voice.command(name="toggle")
    async def toggle_voice_function(self, ctx: commands.Context):
        """Enable/disable the voice generation function."""
        guild_conf = self.config.guild(ctx.guild)

        provider = await guild_conf.function_calling_voice_provider()
        provider = provider.strip().lower()

        enabled_tools: list = await guild_conf.function_calling_functions() or []
        enabling = names.VOICE_REQUEST not in enabled_tools

        if enabling:
            key_error = await provider_key_error(self.bot, ctx, provider)
            if key_error:
                return await ctx.send(key_error)

            enabled_tools.append(names.VOICE_REQUEST)
        else:
            if names.VOICE_REQUEST in enabled_tools:
                enabled_tools.remove(names.VOICE_REQUEST)

        await guild_conf.function_calling_functions.set(enabled_tools)

        embed = discord.Embed(
            title="Voice Request function calling now set to:",
            description=f"`{enabling}`",
            color=await ctx.embed_color(),
        )

        await ctx.send(embed=embed)

    @functions_voice.command(name="provider")
    async def set_voice_provider(self, ctx: commands.Context, provider: str):
        """Set the voice provider.
        Available providers: `elevenlab`, `openai`, `openrouter`, `finevoice`
        """
        provider = provider.strip().lower()

        if provider not in PROVIDERS:
            return await ctx.send(
                "Available voice providers: " + ", ".join(f"`{p}`" for p in PROVIDERS)
            )

        key_error = await provider_key_error(self.bot, ctx, provider)
        if key_error:
            return await ctx.send(key_error)

        guild_conf = self.config.guild(ctx.guild)
        previous_provider = await guild_conf.function_calling_voice_provider()
        previous_provider = previous_provider.strip().lower()

        if previous_provider != provider:
            await self._save_current_voice_provider_settings(
                guild_conf, previous_provider
            )
            await guild_conf.function_calling_voice_provider.set(provider)
            model, voice, restored = await self._restore_voice_provider_settings(
                guild_conf, provider
            )
        else:
            await guild_conf.function_calling_voice_provider.set(provider)
            model = await guild_conf.function_calling_voice_model()
            voice = await guild_conf.function_calling_voice()
            restored = False

        embed = discord.Embed(
            title="Voice provider now set to:",
            description=f"`{provider}`",
            color=await ctx.embed_color(),
        )
        if restored:
            embed.add_field(
                name="🔄 Restored",
                value="Restored previously set model and voice for this provider.",
                inline=False,
            )
        embed.add_field(name="Model", value=f"`{model}`", inline=True)
        embed.add_field(name="Voice", value=f"`{voice}`", inline=True)

        await ctx.send(embed=embed)

    @functions_voice.command(name="model")
    async def set_voice_model(
        self, ctx: commands.Context, *, model: Optional[str] = None
    ):
        """Set the voice model name that may be used by a supported provider."""
        model = model.strip() if model else None
        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.function_calling_voice_model.set(model)

        embed = discord.Embed(
            title="Voice model now set to:",
            description=f"`{model or 'not set'}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @functions_voice.command(name="id")
    async def set_voice_name(
        self, ctx: commands.Context, *, voice: Optional[str] = None
    ):
        """Set the voice name / ID that may be used by a supported provider."""
        voice = voice.strip() if voice else None
        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.function_calling_voice.set(voice)

        embed = discord.Embed(
            title="Voice name now set to:",
            description=f"`{voice or 'not set'}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
