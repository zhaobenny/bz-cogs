import random

import discord

from aiuser.functions.discord.reaction import message_preview

DISCORD_INFO_TYPES = ("channel", "server", "author", "server_emojis")


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def format_dt(value) -> str:
    if not value:
        return "unknown"
    return value.isoformat()


def format_channel(channel: discord.abc.GuildChannel) -> str:
    lines = [
        "Discord channel info:",
        f"- name: #{channel.name}",
        f"- mention: {channel.mention}",
        f"- id: {channel.id}",
        f"- type: {channel.type}",
        f"- created_at: {format_dt(channel.created_at)}",
    ]

    category = getattr(channel, "category", None)
    if category:
        lines.append(f"- category: {category.name}")

    topic = getattr(channel, "topic", None)
    if topic:
        lines.append(f"- topic: {message_preview(topic)}")

    if isinstance(channel, discord.Thread):
        parent = channel.parent
        owner = channel.owner
        applied_tags = [
            tag.name
            for tag in getattr(channel, "applied_tags", [])
            if getattr(tag, "name", None)
        ]
        lines.extend(
            [
                f"- parent: #{parent.name if parent else 'unknown'}",
                f"- owner: {owner.display_name if owner else 'unknown'}",
                f"- applied_tags: {', '.join(applied_tags) if applied_tags else 'none'}",
                f"- archived: {format_bool(channel.archived)}",
                f"- locked: {format_bool(channel.locked)}",
            ]
        )
    else:
        nsfw = getattr(channel, "nsfw", None)
        slowmode = getattr(channel, "slowmode_delay", None)
        if nsfw is not None:
            lines.append(f"- nsfw: {format_bool(nsfw)}")
        if slowmode is not None:
            lines.append(f"- slowmode_seconds: {slowmode}")

    return "\n".join(lines)


def format_server(guild: discord.Guild, me: discord.Member) -> str:
    features = ", ".join(guild.features[:8]) if guild.features else "none"
    lines = [
        "Discord server info:",
        f"- name: {guild.name}",
        f"- id: {guild.id}",
        f"- member_count: {guild.member_count or 'unknown'}",
        f"- owner_id: {guild.owner_id}",
        f"- created_at: {format_dt(guild.created_at)}",
        f"- boost_tier: {guild.premium_tier}",
        f"- boost_count: {guild.premium_subscription_count or 0}",
        f"- preferred_locale: {guild.preferred_locale}",
        f"- features_sample: {features}",
        f"- bot_display_name: {me.display_name}",
    ]
    return "\n".join(lines)


async def format_author(request) -> str:
    author = request.ctx.author
    app_info = await request.bot.application_info()
    owner = app_info.owner
    lines = [
        "Discord author info:",
        f"- display_name: {getattr(author, 'display_name', author.name)}",
        f"- global_name: {author.global_name or 'none'}",
        f"- username: {author.name}",
        f"- mention: {author.mention}",
        f"- id: {author.id}",
        f"- bot: {format_bool(author.bot)}",
        f"- system: {format_bool(getattr(author, 'system', False))}",
        f"- created_at: {format_dt(author.created_at)}",
        f"- is_server_owner: {format_bool(author.id == request.ctx.guild.owner_id)}",
        f"- is_bot_owner: {format_bool(author.id == owner.id)}",
    ]

    if isinstance(author, discord.Member):
        roles = [role.name for role in author.roles if role.name != "@everyone"]
        random.shuffle(roles)
        lines.extend(
            [
                f"- joined_at: {format_dt(author.joined_at)}",
                f"- nick: {author.nick or 'none'}",
                f"- premium_since: {format_dt(author.premium_since)}",
                f"- top_role: {author.top_role.name}",
                f"- roles: {', '.join(roles) if roles else 'none'}",
            ]
        )

    return "\n".join(lines)


def format_server_emojis(guild: discord.Guild) -> str:
    usable = [emoji for emoji in guild.emojis if emoji.is_usable()]
    random.shuffle(usable)
    if usable:
        return "Discord server emoji info:\n" + " ".join(str(emoji) for emoji in usable)
    return "Discord server emoji info:\nnone"


async def get_discord_info(request, info: str) -> str:
    info = str(info).strip()

    if info not in DISCORD_INFO_TYPES:
        return "Invalid info type. Use one of: " + ", ".join(DISCORD_INFO_TYPES) + "."

    if info == "channel":
        return format_channel(request.ctx.channel)
    if info == "server":
        return format_server(request.ctx.guild, request.ctx.me)
    if info == "author":
        return await format_author(request)
    if info == "server_emojis":
        return format_server_emojis(request.ctx.guild)

    return "No Discord info found."
