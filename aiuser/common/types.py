from typing import Union

import discord

COMPATIBLE_CHANNELS = Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.ForumChannel]
COMPATIBLE_MENTIONS = Union[discord.Member, discord.Role, COMPATIBLE_CHANNELS]
