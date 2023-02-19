from redbot.core import commands
import aiohttp
from discord import Embed
import pytz
from datetime import datetime


CHECKMARK = {
    "on": "✅",
    "off": "⛔"
}


class BZLight(commands.Cog):
    """ yup, exposing my light to the discord server lol """
    lifx_token = None
    forceDisabled = False
    light_id = "id%3Ad073d55b6334"

    def __init__(self, bot):
        self.session = aiohttp.ClientSession()
        self.bot = bot

    def isDisabled(self):
        vancouver_tz = pytz.timezone('America/Vancouver')
        vancouver_hour = datetime.now(vancouver_tz).hour
        return (vancouver_hour >= 22 or vancouver_hour < 12 or self.forceDisabled)

    async def initialize_lifx_key(self, ctx):
        shared_token = await self.bot.get_shared_api_tokens("lifx")
        if shared_token.get("api_key") is None:
            await ctx.send("The Lifx API key has not been set! Get your key from Lifx cloud and use [p]set api lifx api_key,INSERT_API_KEY")
            return
        self.lifx_token = shared_token.get("api_key")
        return

    async def lifx_post(self, endpoint, payload, ctx):
        if self.lifx_token is None:
            await self.initialize_lifx_key(ctx)

        headers = {
            "Authorization": "Bearer %s" % self.lifx_token,
        }
        response = await(await self.session.post(f"https://api.lifx.com/v1/lights/{self.light_id}/{endpoint}", json=payload, headers=headers)).json()

        if response["results"][0]["status"] != "ok":
            return (False, response)

        return (True, response)

    @commands.group(no_pm=True, invoke_without_command=True)
    async def light(self, ctx):
        if self.lifx_token is None:
            await self.initialize_lifx_key(ctx)
        else:
            await ctx.send("[p]help light for commands to run")

    @light.command()
    async def toggle(self, ctx):
        """ Toggles the light """
        if self.isDisabled() and ctx.author.id != 269670939480817664:
            await ctx.send("Not doing that.")
            return

        success, res = await self.lifx_post("toggle", {"duration": 1}, ctx)

        if success is not True:
            await ctx.send("it broke")
            return

        power_state = "on" if res["results"][0]["power"] == "on" else "off"
        await ctx.send(f"Congrats you just turned {CHECKMARK[power_state]} Benny's light")

    @light.command()
    async def alarm(self, ctx):
        """ Wee wooo wee ooo """
        if self.isDisabled():
            await ctx.send("Go alarm yourself instead.")
            return

        success, _ = await self.lifx_post("effects/pulse", {
            "period": 1,
            "cycles": 5,
            "persist": False,
            "power_on": True,
            "color": "kelvin:2000"
        }, ctx)

        if success is not True:
            await ctx.send("alarm broke")
            return

        await ctx.send("🚨 ALARM has BEEN RAISED IN BZ ROOM 🚨")


    @light.command()
    async def strobe(self, ctx):
        """ Epilepsy """
        if self.isDisabled():
            await ctx.send("Go strobe something else.")
            return

        success, _ = await self.lifx_post("effects/pulse", {
            "period": 0.1,
            "cycles": 50,
            "persist": False,
            "power_on": True,
            "color": "kelvin:7500 brightness:1"
        }, ctx)

        if success is not True:
            await ctx.send("epilepsy attck no work")
            return

        await ctx.send("epilepsy attack send")

    @light.command()
    async def disable(self, ctx):
        """ Master disable switch """
        if ctx.author.id != 269670939480817664:
            await ctx.send("you are not bz")
        self.forceDisabled = not self.forceDisabled
        if (self.forceDisabled):
            await ctx.send("Disabled all light cmds")
        else:
            await ctx.send("Enabled all light cmds")

    @light.command()
    async def status(self, ctx):
        """ Status check """
        if self.lifx_token is None:
            await self.initialize_lifx_key(ctx)

        headers = {
            "Authorization": "Bearer %s" % self.lifx_token,
        }
        res = await (await self.session.get('https://api.lifx.com/v1/lights/all', headers=headers)).json()

        embed = Embed(title="Benny's Light Status", color=0xFFD300)

        for light in res:
            light_label = light["label"]
            light_power = light["power"]
            light_brightness = light["brightness"]
            light_color = light["color"]
            light_color_kelvin = light_color["kelvin"]

            embed.add_field(name=light_label, value=f"\
                Power: {CHECKMARK[light_power]} \n\
                Brightness: {light_brightness} \n\
                Kelvin: {light_color_kelvin} \n\
            ")

        await ctx.send(embed=embed)

    def cog_unload(self):
        if (self.session):
            self.session.close()
