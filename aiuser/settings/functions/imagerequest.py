import discord
from redbot.core import commands

from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions
from aiuser.types.abc import MixinMeta


class ImageRequestFunctionSettings(MixinMeta, FunctionToggleHelperMixin):
    @functions.group(name="imagerequest")
    async def imagerequest(self, ctx: commands.Context): 
        """ Image generation function settings (per server) """
        pass

    @imagerequest.command(name="toggle")
    async def imagerequest_toggle(self, ctx: commands.Context):
        from aiuser.functions.imagerequest.tool_call import ImageRequestToolCall
        await self.toggle_function_group(ctx, [ImageRequestToolCall.function_name], "Image Request")

    @imagerequest.command(name="endpoint")
    async def imagerequest_endpoint(self, ctx: commands.Context, *, endpoint: str = None):
        await self.config.guild(ctx.guild).function_calling_image_custom_endpoint.set(endpoint or None)
        e = discord.Embed(title="Image request endpoint set to:", description=f"{endpoint or 'Autodetected'}", color=await ctx.embed_color())
        await ctx.send(embed=e)

    @imagerequest.command(name="model")
    async def imagerequest_model(self, ctx: commands.Context, *, model: str = None):
        await self.config.guild(ctx.guild).function_calling_image_model.set(model or None)
        desc = f"{model}" if model else "Default"
        e = discord.Embed(title="Image request model set to:", description=desc, color=await ctx.embed_color())
        await ctx.send(embed=e)

    @imagerequest.command(name="preprompt")
    async def imagerequest_preprompt(self, ctx: commands.Context, *, preprompt: str = None):
        limit = 3200
        if preprompt and len(preprompt) > limit:
            return await ctx.send(f"Preprompt too long ({len(preprompt)}/{limit}). Please shorten it.")
        await self.config.guild(ctx.guild).function_calling_image_preprompt.set(preprompt or None)
        e = discord.Embed(title="Image request preprompt set to:", description=f"{(preprompt or 'Cleared')}", color=await ctx.embed_color())
        await ctx.send(embed=e)
