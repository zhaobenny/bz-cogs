"""Shared command-group stubs for the settings mixins.

How this works: discord.py's cog machinery re-parents subcommands onto the
command with the same qualified name defined on the *final* cog class. So the
mixins in this package attach their subcommands to the module-level stub
below, and :class:`aiuser.settings.base.Settings` defines the real ``aiuser``
group that everything is re-parented onto when the cog is constructed.

(The same pattern applies one level down for the ``functions`` group in
``aiuser.settings.functions.utilities``.)
"""

from redbot.core import commands


@commands.group(aliases=["ai_user"])
@commands.guild_only()
async def aiuser(self, _):
    """Utilize OpenAI to reply to messages and images in approved channels"""
    pass
