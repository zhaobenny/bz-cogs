from datetime import datetime
from redbot.core import commands


def format_variables(ctx: commands.Context, text: str):
    """
        Formats a string with the specific variables
    """
    botname = ctx.message.guild.me.nick or ctx.bot.user.display_name
    authorname = ctx.message.author.display_name
    servername = ctx.guild.name
    channelname = ctx.message.channel.name
    currentdate = datetime.today().strftime("%Y/%m/%d")
    currentweekday = datetime.today().strftime("%A")
    currenttime = datetime.today().strftime("%H:%M")

    return text.format(
        botname=botname,
        authorname=authorname,
        servername=servername,
        channelname=channelname,
        currentdate=currentdate,
        currentweekday=currentweekday,
        currenttime=currenttime,
    )
