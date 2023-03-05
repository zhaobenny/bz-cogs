from .lifx_light import LifxLight

def setup(bot):
    bot.add_cog(LifxLight(bot))