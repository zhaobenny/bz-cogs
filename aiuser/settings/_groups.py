from redbot.core import commands


@commands.group(aliases=["ai_user"])
@commands.guild_only()
async def aiuser(self, _):
    """Configure replies to messages and images in enabled reply channels"""
    pass
