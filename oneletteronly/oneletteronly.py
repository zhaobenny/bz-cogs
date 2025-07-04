import discord
from redbot.core import commands, Config, checks
from redbot.core.i18n import Translator, cog_i18n

_ = Translator("oneletteronly", __file__)


@cog_i18n(_)
class oneletteronly(commands.Cog):
    """{0}""".format(_("Changes new user's nickname to first letter of nickname"))

    __version__ = "2.0"
    __author__ = "zhaobenny"
    __contributor__ = "evanroby"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=754070)
        default_guild = {
            "enabled": False,
        }
        self.config.register_guild(**default_guild)

    def format_help_for_context(self, ctx):
        pre_processed = super().format_help_for_context(ctx)
        n = "\n" if "\n\n" not in pre_processed else ""
        return (
            f"{pre_processed}{n}\n"
            f"{_('Cog Version')}: {self.__version__}\n"
            f"{_('Cog Author')}: {self.__author__}\n"
            f"{_('Cog Contributor')}: {self.__contributor__}"
        )

    @commands.guild_only()
    @checks.admin_or_permissions(manage_nicknames=True)
    @commands.command(name="oneletteronly")
    async def oneletteronly_toggle(self, ctx: commands.Context):
        """{0}""".format(
            _("Toggle if the bot should change new user's nickname to first letter of nickname")
        )
        guild = ctx.guild
        enabled = await self.config.guild(guild).enabled()
        await self.config.guild(guild).enabled.set(not enabled)

        if enabled:
            await ctx.send(_("Disabled"))
        else:
            await ctx.send(_("Enabled"))

    @commands.guild_only()
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not await self.config.guild(member.guild).enabled():
            return

        words = member.name.split()
        if member.bot:
            new_nick = "!" + words[0][0].upper()
        elif len(words) >= 2:
            new_nick = (words[0][0] + words[1][0]).upper()
        else:
            new_nick = words[0][0].upper()

        try:
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            pass
