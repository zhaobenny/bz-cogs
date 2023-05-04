from .lifx_light import LifxLight

async def setup(bot):
    await bot.add_cog(LifxLight(bot))