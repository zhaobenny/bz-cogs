import discord
from redbot.core import commands, Config, checks


class oneletteronly(commands.Cog):
    """Changes new user's nickname to first letter of nickname"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=754070)
        default_guild = {
            "enabled": False,
        }
        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @checks.admin_or_permissions(manage_nicknames=True)
    @commands.command()
    async def oneletteronly(self, message):
        """ Toggle if the bot should change new user's nickname to first letter of nickname """
        guild = message.guild
        if await self.config.guild(guild).enabled():
            await self.config.guild(guild).enabled.set(False)
            return await message.send("Disabled")
        else:
            await self.config.guild(guild).enabled.set(True)
            return await message.send("Enabled")


    @commands.guild_only()
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        if not (await self.config.guild(member.guild).enabled()):
            return

        words = member.name.split()
        if (member.bot):
            new_nick = "!" + words[0][0].upper()
        elif (len(words) >= 2):
            new_nick = (words[0][0] + words[1][0]).upper()
        else:
            new_nick = words[0][0].upper()

        await member.edit(nick=new_nick)

        return
