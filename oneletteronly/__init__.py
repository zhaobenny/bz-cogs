from .oneletteronly import oneletteronly


async def setup(bot):
    await bot.add_cog(oneletteronly(bot))
