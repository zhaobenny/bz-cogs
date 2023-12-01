
import discord
from redbot.core import checks

from aiuser.abc import MixinMeta, aiuser
from aiuser.common.constants import FUNCTION_CALLING_SUPPORTED_MODELS


class FunctionCallingSettings(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def functions(self, ctx):
        """Function calling settings"""
        pass

    @functions.command(name="toggle")
    async def toggle_function_calling(self, ctx):
        """Toggle functions calling """

        current_value = not await self.config.guild(ctx.guild).function_calling()

        if current_value:
            model = await self.config.guild(ctx.guild).model()
            if model not in FUNCTION_CALLING_SUPPORTED_MODELS:
                return await ctx.send(f":warning: Currently selected model, {model}, does not support function calling. Set a comptaible model first!")

        await self.config.guild(ctx.guild).function_calling.set(current_value)

        embed = discord.Embed(
            title="Functions Calling now set to:",
            description=f"{current_value}",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
