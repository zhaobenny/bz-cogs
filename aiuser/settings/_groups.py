from redbot.core import commands


@commands.group(aliases=["ai_user"])
@commands.guild_only()
async def aiuser(self, _):
    """Utilize OpenAI to reply to messages and images in approved channels"""
    pass
