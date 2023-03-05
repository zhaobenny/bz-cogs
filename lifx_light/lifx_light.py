from datetime import datetime

import aiohttp
import pytz
from discord import Embed
from redbot.core import Config, checks, commands

CHECKMARK = {
    "on": "✅",
    "off": "⛔"
}


class LifxLight(commands.Cog):
    lifx_token = None
    forceDisabled = None
    light_id = None
    timezone = None
    owner_name = None
    night_disable = None

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=354173)
        default_global = {
            "night_disable": False,
            "timezone": "America/Vancouver",
            "force_disabled": False,
            "light_id": None,
            "owner_display_name": "owner"
        }
        self.config.register_global(**default_global)

    async def update_cache(self):
        if not self.night_disable: # if this is not set, all values are not set
            self.night_disable = await self.config.night_disable()
            self.timezone = await self.config.timezone()
            self.forceDisabled = await self.config.force_disabled()
            self.light_id = await self.config.light_id()
            self.owner_name = await self.config.owner_display_name()

    async def isDisabled(self):
        await self.update_cache()
        if not self.night_disable:
            tz = pytz.timezone(self.timezone)
            hour = datetime.now(tz).hour
            night = hour >= 22 or hour < 12
        else:
            night = False
        return (night or self.forceDisabled)

    async def initialize_lifx_key(self, ctx):
        shared_token = await self.bot.get_shared_api_tokens("lifx")
        if shared_token.get("api_key") is None:
            return await ctx.send("The Lifx API key has not been set! Get your key from Lifx cloud and use [p]set api lifx api_key,INSERT_API_KEY")
        self.lifx_token = shared_token.get("api_key")
        return

    async def lifx_post(self, endpoint, payload, ctx):
        print(self.light_id)
        print(await self.config.light_id())
        if self.lifx_token is None:
            await self.initialize_lifx_key(ctx)
        if self.light_id is None:
            await ctx.send("Light ID not set, use [p]light setting id INSERT_ID")
            return (False, "")

        headers = {
            "Authorization": "Bearer %s" % self.lifx_token,
        }
        async with aiohttp.ClientSession() as session:
            response = await(await session.post(f"https://api.lifx.com/v1/lights/{self.light_id}/{endpoint}", json=payload, headers=headers)).json()

        if response["results"][0]["status"] != "ok":
            return (False, response)

        return (True, response)

    @commands.group(pass_context=True)
    async def light(self, ctx):
        pass

    @light.group()
    async def setting(self, ctx):
        """ Light settings """
        pass

    @setting.command()
    @checks.is_owner()
    async def id(self, ctx, light_id):
        """ Set to a selector, see https://api.developer.lifx.com/docs/selectors """
        await self.config.light_id.set(light_id)
        self.light_id = light_id
        await ctx.send(f"Light ID set to {light_id}")

    @setting.command()
    @checks.is_owner()
    async def disable_night(self, ctx, value: bool):
        """ Set whether the commands should be automatically disabled at night (Default: False)"""
        await self.config.night_disable.set(value)
        self.night_disable = value
        await ctx.send(f"Night mode disable set to {value}")

    @setting.command()
    @checks.is_owner()
    async def timezone_str(self, ctx, timezone: str):
        """ Set the timezone for the night_disable (Default: "America/Vancouver") """
        await self.config.timezone.set(timezone)
        self.timezone = timezone
        await ctx.send(f"Timezone set to {timezone}")

    @setting.command()
    @checks.is_owner()
    async def ownername(self, ctx, name: str):
        """ Set the owner's display name """
        await self.config.owner_display_name.set(name)
        self.owner_name = name
        await ctx.send(f"Owner display name set to {name}")


    @light.command()
    async def toggle(self, ctx):
        """ Toggles the light """
        if await self.isDisabled():
            await ctx.send("Not doing that.")
            return

        success, res = await self.lifx_post("toggle", {"duration": 1}, ctx)

        if success is not True:
            await ctx.send("it broke")
            return

        power_state = "on" if res["results"][0]["power"] == "on" else "off"
        await ctx.send(f"Congrats you just turned {CHECKMARK[power_state]} {self.owner_name}'s light")

    @light.command()
    async def alarm(self, ctx):
        """ Wee wooo wee ooo """
        if await self.isDisabled():
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

        await ctx.send(f"🚨 ALARM has BEEN RAISED IN {self.owner_name} ROOM 🚨")


    @light.command()
    async def strobe(self, ctx):
        """ Epilepsy """
        if await self.isDisabled():
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
    @commands.is_owner()
    async def disable(self, ctx):
        """ Master disable switch """
        self.forceDisabled = not (await self.config.forceDisabled())
        await self.config.forceDisabled.set(self.forceDisabled)
        if (self.forceDisabled):
            await ctx.send("Disabled all light cmds")
        else:
            await ctx.send("Enabled all light cmds")

    @light.command()
    async def status(self, ctx):
        """ Status check """
        if self.lifx_token is None:
            await self.initialize_lifx_key(ctx)
            await self.update_cache()

        headers = {
            "Authorization": "Bearer %s" % self.lifx_token,
        }
        res = await (await aiohttp.ClientSession().get('https://api.lifx.com/v1/lights/all', headers=headers)).json()

        embed = Embed(title=f"{self.owner_name}'s Lights Status", color=0xFFD300)

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

