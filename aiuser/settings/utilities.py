import discord
import tiktoken
from openai import AsyncOpenAI
from redbot.core import Config, commands

from aiuser.types.enums import MentionType
from aiuser.utils.utilities import (
    encode_text_to_tokens,
    format_variables,
    is_using_openai_endpoint,
    is_using_openrouter_endpoint,
)


async def get_available_models(openai_client: AsyncOpenAI) -> list[str]:
    res = await openai_client.models.list()

    if is_using_openai_endpoint(openai_client):
        models = [
            model.id
            for model in res.data
            if ("gpt" in model.id or "o3" in model.id.lower())
            and "audio" not in model.id.lower()
            and "realtime" not in model.id.lower()
        ]
    elif is_using_openrouter_endpoint(openai_client):
        models = sorted(
            [model.id for model in res.data],
            key=lambda m: (
                0
                if any(kw in m.lower() for kw in ["gpt", "gemini", "meta-llama"])
                else 1,
                m,
            ),
        )
    else:
        models = [model.id for model in res.data]
    return models


def get_mention_type(mention) -> MentionType:
    if isinstance(mention, discord.Member):
        return MentionType.USER
    elif isinstance(mention, discord.Role):
        return MentionType.ROLE
    elif isinstance(
        mention,
        (
            discord.TextChannel,
            discord.VoiceChannel,
            discord.StageChannel,
            discord.ForumChannel,
        ),
    ):
        return MentionType.CHANNEL
    else:
        return MentionType.SERVER


def get_config_attribute(
    config, mention_type: MentionType, ctx: commands.Context, mention
):
    if mention_type == MentionType.SERVER:
        return config.guild(ctx.guild)
    elif mention_type == MentionType.USER:
        return config.member(mention)
    elif mention_type == MentionType.ROLE:
        return config.role(mention)
    elif mention_type == MentionType.CHANNEL:
        return config.channel(mention)


async def get_tokens(config: Config, ctx: commands.Context, prompt: str) -> int:
    if not prompt:
        return 0
    prompt = await format_variables(ctx, prompt)  # to provide a better estimate
    return await encode_text_to_tokens(prompt, await config.guild(ctx.guild).model())


def truncate_prompt(prompt: str, limit: int = 1900) -> str:
    if len(prompt) > limit:
        return prompt[:limit] + "..."
    return prompt
