from .bittensorimg import BitTensorImg


async def setup(bot):
    await bot.add_cog(BitTensorImg(bot))
