from typing import Optional

import discord
from redbot.core import commands

from aiuser.functions import names
from aiuser.providers.speech.tts import DEFAULT_MODELS, DEFAULT_VOICES, PROVIDERS
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

    @functions_voice.command(name="show")
    async def show_voice_function(self, ctx: commands.Context):
        """Show voice generation tool settings."""
        guild_conf = self.config.guild(ctx.guild)
        provider = await guild_conf.function_calling_voice_provider()
        enabled_tools: list = await guild_conf.function_calling_functions() or []
        model = await guild_conf.function_calling_voice_model()
        voice = await guild_conf.function_calling_voice()
        embed = discord.Embed(
            title="Voice tool settings", color=await ctx.embed_color()
        )
        embed.add_field(
            name="Enabled",
            value="Yes" if names.VOICE_REQUEST in enabled_tools else "No",
        )
        embed.add_field(name="Provider", value=f"`{provider}`")
        embed.add_field(name="Model", value=f"`{model or 'Default'}`")
        embed.add_field(name="Voice", value=f"`{voice or 'Default'}`")
        return await ctx.send(embed=embed)

    @functions_voice.command(name="enable")
    async def enable_voice_function(self, ctx: commands.Context):
        """Enable the voice generation tool."""
        provider = await self.config.guild(ctx.guild).function_calling_voice_provider()
        key_error = await provider_key_error(self.bot, ctx, provider.strip().lower())
        if key_error:
            return await ctx.send(key_error)
        return await self.set_function_group(ctx, [names.VOICE_REQUEST], "Voice", True)

    @functions_voice.command(name="disable")
    async def disable_voice_function(self, ctx: commands.Context):
        """Disable the voice generation tool."""
        return await self.set_function_group(ctx, [names.VOICE_REQUEST], "Voice", False)

    @functions_voice.group(name="provider", invoke_without_command=True)
    async def voice_provider(self, ctx: commands.Context):
        """Show the voice generation provider"""
        provider = await self.config.guild(ctx.guild).function_calling_voice_provider()
        return await ctx.maybe_send_embed(f"Voice provider: `{provider}`")

    @voice_provider.command(name="set")
    async def set_voice_provider(self, ctx: commands.Context, provider: str):
        """Set the voice generation provider"""
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

    @functions_voice.group(name="model", invoke_without_command=True)
    async def voice_model(self, ctx: commands.Context):
        """Show the voice generation model"""
        model = await self.config.guild(ctx.guild).function_calling_voice_model()
        return await ctx.maybe_send_embed(f"Voice model: `{model or 'Default'}`")

    @voice_model.command(name="set")
    async def set_voice_model(self, ctx: commands.Context, *, model: str):
        """Set the voice generation model"""
        await self.config.guild(ctx.guild).function_calling_voice_model.set(
            model.strip()
        )
        return await ctx.send(f"Voice model set to `{model.strip()}`.")

    @voice_model.command(name="clear")
    async def clear_voice_model(self, ctx: commands.Context):
        """Use the voice provider's default model"""
        await self.config.guild(ctx.guild).function_calling_voice_model.set(None)
        return await ctx.send("Voice model reset to the provider default.")

    @functions_voice.group(name="voice_id", aliases=["id"], invoke_without_command=True)
    async def voice_id(self, ctx: commands.Context):
        """Show the voice name or ID"""
        voice = await self.config.guild(ctx.guild).function_calling_voice()
        return await ctx.maybe_send_embed(f"Voice name or ID: `{voice or 'Default'}`")

    @voice_id.command(name="set")
    async def set_voice_name(self, ctx: commands.Context, *, voice: str):
        """Set the voice name or ID"""
        await self.config.guild(ctx.guild).function_calling_voice.set(voice.strip())
        return await ctx.send(f"Voice name or ID set to `{voice.strip()}`.")

    @voice_id.command(name="clear")
    async def clear_voice_name(self, ctx: commands.Context):
        """Use the voice provider's default voice"""
        await self.config.guild(ctx.guild).function_calling_voice.set(None)
        return await ctx.send("Voice reset to the provider default.")
