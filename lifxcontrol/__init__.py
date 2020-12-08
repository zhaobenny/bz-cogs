from .lifxcontrol import LifxControl

def setup(bot):
    bot.add_cog(LifxControl(bot))