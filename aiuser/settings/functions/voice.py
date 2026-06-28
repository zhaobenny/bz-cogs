from typing import Optional

import discord
from redbot.core import commands

from aiuser.functions import names
from aiuser.functions.voice.providers.factory import (
    ELEVENLAB,
    FINEVOICE,
    OPENROUTER,
    PROVIDERS,
)
from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions


class VoiceFunctionSettings(FunctionToggleHelperMixin):
    async def _voice_provider_key_error(
        self, ctx: commands.Context, provider: str
    ) -> Optional[str]:
        tokens = await self.bot.get_shared_api_tokens(provider)
        if tokens.get("api_key"):
            return None

        return (
            f"{provider} key not set! Set it using "
            f"`{ctx.clean_prefix}set api {provider} api_key,APIKEY`."
        )

    async def _voice_setup_warnings(
        self, ctx: commands.Context, provider: str
    ) -> list[str]:
        guild_conf = self.config.guild(ctx.guild)
        warnings: list[str] = []

        if provider == ELEVENLAB:
            if not (await guild_conf.function_calling_voice()):
                warnings.append(
                    f"- Voice ID: `{ctx.clean_prefix}aiuser functions voice id <voice>`"
                )

        elif provider == FINEVOICE:
            if not (await guild_conf.function_calling_voice()):
                warnings.append(
                    f"- Voice ID: `{ctx.clean_prefix}aiuser functions voice id <voice>`"
                )

        elif provider == OPENROUTER:
            if not (await guild_conf.function_calling_voice_model()):
                warnings.append(
                    f"- Model: `{ctx.clean_prefix}aiuser functions voice model <model>`"
                )
            if not (await guild_conf.function_calling_voice()):
                warnings.append(
                    f"- Voice ID: `{ctx.clean_prefix}aiuser functions voice id <voice>`"
                )

        return warnings

    def _format_voice_setup_warnings(self, warnings: list[str]) -> Optional[str]:
        if not warnings:
            return None

        return (
            "**⚠️ Setup Incomplete**\n\n"
            "Configure the following for voice generation to work:\n"
            + "\n".join(warnings)
        )

    @functions.group(name="voice")
    async def functions_voice(self, ctx: commands.Context):
        """Voice generation function settings (per server)."""
        pass

    @functions_voice.command(name="toggle")
    async def toggle_voice_function(self, ctx: commands.Context):
        """Enable/disable the voice generation function."""
        guild_conf = self.config.guild(ctx.guild)

        provider = await guild_conf.function_calling_voice_provider()
        provider = (provider or OPENROUTER).strip().lower()

        enabled_tools: list = await guild_conf.function_calling_functions() or []
        enabling = names.VOICE_REQUEST not in enabled_tools

        if enabling:
            key_error = await self._voice_provider_key_error(ctx, provider)
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

        if enabling:
            warnings = await self._voice_setup_warnings(ctx, provider)
            warning_text = self._format_voice_setup_warnings(warnings)
            if warning_text:
                embed.description += f"\n\n{warning_text}"

        await ctx.send(embed=embed)

    @functions_voice.command(name="provider")
    async def set_voice_provider(self, ctx: commands.Context, provider: str):
        """Set the voice provider.
        Available providers: `elevenlab`, `openrouter`, `finevoice`
        """
        provider = provider.strip().lower()

        if provider not in PROVIDERS:
            return await ctx.send(
                "Available voice providers: " + ", ".join(f"`{p}`" for p in PROVIDERS)
            )

        key_error = await self._voice_provider_key_error(ctx, provider)
        if key_error:
            return await ctx.send(key_error)

        guild_conf = self.config.guild(ctx.guild)
        await guild_conf.function_calling_voice_provider.set(provider)

        embed = discord.Embed(
            title="Voice provider now set to:",
            description=f"`{provider}`",
            color=await ctx.embed_color(),
        )

        warnings = await self._voice_setup_warnings(ctx, provider)
        warning_text = self._format_voice_setup_warnings(warnings)
        if warning_text:
            embed.description += f"\n\n{warning_text}"

        await ctx.send(embed=embed)

    @functions_voice.command(name="model")
    async def set_voice_model(
        self, ctx: commands.Context, *, model: Optional[str] = None
    ):
        """Set the voice model name that may be used by a supported provider."""
        model = model.strip() if model else None
        await self.config.guild(ctx.guild).function_calling_voice_model.set(model)

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
        await self.config.guild(ctx.guild).function_calling_voice.set(voice)

        embed = discord.Embed(
            title="Voice name now set to:",
            description=f"`{voice or 'not set'}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
