import discord
import tiktoken
from redbot.core import Config, commands

from aiuser.common.enums import MentionType
from aiuser.common.utilities import format_variables


def get_mention_type(mention) -> MentionType:
    if isinstance(mention, discord.Member):
        return MentionType.USER
    elif isinstance(mention, discord.Role):
        return MentionType.ROLE
    elif isinstance(mention, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel)):
        return MentionType.CHANNEL
    else:
        return MentionType.SERVER


def get_config_attribute(config, mention_type: MentionType, ctx: commands.Context, mention):
    if mention_type == MentionType.SERVER:
        return config.guild(ctx.guild)
    elif mention_type == MentionType.USER:
        return config.member(mention)
    elif mention_type == MentionType.ROLE:
        return config.role(mention)
    elif mention_type == MentionType.CHANNEL:
        return config.channel(mention)
    else:
        raise ValueError("Invalid mention provided")


async def get_tokens(config: Config, ctx: commands.Context, prompt: str) -> int:
    if not prompt:
        return 0
    prompt = format_variables(ctx, prompt)  # to provide a better estimate
    try:
        encoding = tiktoken.encoding_for_model(await config.guild(ctx.guild).model())
    except KeyError:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    return len(encoding.encode(prompt, disallowed_special=()))


def truncate_prompt(prompt: str) -> str:
    if len(prompt) > 1900:
        return prompt[:1900] + "..."
    return prompt
