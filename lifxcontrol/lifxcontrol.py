import discord
from redbot.core import commands
import aiohttp
import asyncio

class LifxControl(commands.Cog):
    """Surely nothing would go wrong here"""

    lifx_token = None

    def __init__(self, bot):
        self.session = aiohttp.ClientSession()
        self.bot = bot

    async def initialize_lifx_key(self, ctx):
        shared_token = await self.bot.get_shared_api_tokens("lifx")
        if shared_token.get("api_key") is None:
            await ctx.send("The Lifx API key has not been set! Get your key from Lifx cloud and use [p]set api lifx api_key,INSERT_API_KEY")
            return
        self.lifx_token = shared_token.get("api_key")
        return

    @commands.group(no_pm=True, invoke_without_command = True)
    async def lifx(self, ctx):
        if  self.lifx_token is None:
            await self.initialize_lifx_key(ctx)
        else:
            await ctx.send("Your Lifx API key is set already.")

    @lifx.command()
    async def list(self, ctx):
        if  self.lifx_token is None:
            await self.initialize_lifx_key(ctx)
        else:
            headers = {
                "Authorization": "Bearer %s" % self.lifx_token,
            }
            response = await self.session.get('https://api.lifx.com/v1/lights/all', headers=headers)
            # add meaningful display here
            await ctx.send(response)

