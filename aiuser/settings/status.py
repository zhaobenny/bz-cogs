from __future__ import annotations

import json
from typing import Any

import discord

from aiuser.config.constants import RANDOM_MESSAGE_TASK_RETRY_SECONDS
from aiuser.config.defaults import DEFAULT_STT_PROVIDER
from aiuser.providers.decision import resolve_decision_provider
from aiuser.providers.llm.codex.chatgpt import CODEX_ENDPOINT_MODE
from aiuser.providers.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_kind,
)
from aiuser.providers.speech.stt import DEFAULT_MODELS as STT_DEFAULT_MODELS
from aiuser.types.enums import ReplyMode

_MAX_CHANNELS_LENGTH = 900
_MAX_ALLOWLIST_LINE_LENGTH = 350
_MAX_IGNORE_REGEX_LENGTH = 80
_MAX_PARAMETERS_LENGTH = 900


def _state_label(enabled: bool) -> str:
    return "**On**" if enabled else "Off"


def _format_inline_code(value: str, max_length: int | None = None) -> str:
    text = str(value).replace("\n", " ")
    if max_length is not None and len(text) > max_length:
        text = text[: max_length - 3].rstrip() + "..."
    if "`" in text:
        escaped = text.replace("``", "`\u200b`")
        pad = " " if escaped.startswith("`") or escaped.endswith("`") else ""
        return f"``{pad}{escaped}{pad}``"
    return f"`{text}`"


def _format_percent(fraction: float) -> str:
    formatted = f"{fraction * 100:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}%"


def _format_megabytes(size_bytes: float) -> str:
    formatted = f"{size_bytes / (1024 * 1024):.2f}".rstrip("0").rstrip(".")
    return f"{formatted} MB"


def _format_duration(seconds: float) -> str:
    total = max(0, round(seconds))
    if total == 0:
        return "0s"
    parts: list[str] = []
    for unit_seconds, suffix in (
        (86400, "d"),
        (3600, "h"),
        (60, "m"),
        (1, "s"),
    ):
        value, total = divmod(total, unit_seconds)
        if value:
            parts.append(f"{value}{suffix}")
    return " ".join(parts)


def _format_endpoint(endpoint_url: str) -> str:
    if endpoint_url == CODEX_ENDPOINT_MODE:
        return "[OpenAI](https://openai.com/) via Codex"
    if get_openai_compat_kind(endpoint_url) is CompatEndpointKind.OPENROUTER:
        return "[OpenRouter](https://openrouter.ai)"
    if endpoint_url:
        return "Custom endpoint"
    return "[OpenAI](https://openai.com/)"


def _join_bounded(items: list[str], *, max_length: int, sep: str = " ") -> str:
    if not items:
        return "None"
    kept: list[str] = []
    current_length = 0
    for index, item in enumerate(items):
        remaining = len(items) - index
        overflow_suffix = f" (+{remaining} more)"
        projected = current_length + (len(sep) if kept else 0) + len(item)
        if kept and projected + len(overflow_suffix) > max_length:
            return f"{sep.join(kept)}{overflow_suffix}"
        if not kept and len(item) > max_length:
            return item[: max_length - 3].rstrip() + "..."
        kept.append(item)
        current_length = projected
    return sep.join(kept)


def _format_channels(guild: discord.Guild, whitelist: list[int]) -> str:
    channels = [
        channel.mention
        if (channel := guild.get_channel_or_thread(channel_id))
        else f"Unknown ({_format_inline_code(str(channel_id))})"
        for channel_id in whitelist
    ]
    return _join_bounded(channels, max_length=_MAX_CHANNELS_LENGTH)


def _format_tools(config: dict[str, Any]) -> str:
    if not config.get("function_calling"):
        return "Off"
    tool_count = len(config.get("function_calling_functions") or [])
    mcp_count = len(config.get("mcp_enabled_servers") or [])
    details: list[str] = []
    if tool_count:
        details.append(f"{tool_count} {'tool' if tool_count == 1 else 'tools'}")
    if mcp_count:
        details.append(f"{mcp_count} MCP")
    if details:
        return f"**On** ({', '.join(details)})"
    return "**On** (0 active)"


def _format_media_lines(config: dict[str, Any]) -> str:
    if config.get("scan_images"):
        image_model = config.get("scan_images_model")
        model_label = _format_inline_code(image_model) if image_model else "chat model"
        detail = _format_inline_code(config.get("scan_images_detail", "low"))
        max_size = _format_megabytes(config.get("max_image_size", 0))
        images_line = (
            f"Images: **On** · {model_label} · {detail} detail · max {max_size}"
        )
    else:
        images_line = "Images: Off"

    if config.get("scan_audio"):
        stt_provider = (
            config.get("scan_audio_provider") or DEFAULT_STT_PROVIDER
        ).lower()
        stt_model = config.get("scan_audio_model") or STT_DEFAULT_MODELS.get(
            stt_provider
        )
        provider_label = _format_inline_code(stt_provider)
        if stt_model:
            provider_label = f"{provider_label} ({_format_inline_code(stt_model)})"
        max_duration = _format_duration(config.get("max_audio_duration", 0))
        audio_line = f"Audio: **On** · {provider_label} · max {max_duration}"
    else:
        audio_line = "Audio: Off"

    return f"{images_line}\n{audio_line}"


def _format_parameters_field(raw_parameters: Any, prefix: str) -> str | None:
    if not raw_parameters:
        return None
    try:
        parsed = json.loads(raw_parameters)
    except (TypeError, json.JSONDecodeError):
        return f"Invalid JSON stored. Check `{prefix}aiuser response parameters`."
    if not parsed:
        return None
    formatted = json.dumps(parsed, indent=2)
    if len(formatted) <= _MAX_PARAMETERS_LENGTH:
        return f"```json\n{formatted}\n```"
    note = f"\nRun `{prefix}aiuser response parameters` to view all."
    budget = _MAX_PARAMETERS_LENGTH - len(note) - 16
    preview = formatted[:budget].rstrip() + "\n..."
    return f"```json\n{preview}\n```{note}"


async def build_status_embed(
    *,
    ctx: Any,
    services: Any,
    version: str,
    config: dict[str, Any],
    glob_config: dict[str, Any],
    default_model: str,
    whitelist: list[int],
    color: discord.Color,
) -> discord.Embed:
    guild_model = config.get("model")
    active_model = guild_model or default_model
    model_text = _format_inline_code(active_model)
    if not guild_model:
        model_text = f"{model_text} (default)"

    endpoint_url = str(glob_config.get("custom_openai_endpoint") or "")
    endpoint_text = _format_endpoint(endpoint_url)
    channels_text = _format_channels(ctx.guild, whitelist)

    embed = discord.Embed(
        title="AI User Settings",
        description=(
            f"**Model:** {model_text} · {endpoint_text}\n**Channels:** {channels_text}"
        ),
        color=color,
    )

    reply_mode = ReplyMode.from_raw(config.get("reply_mode"))
    if reply_mode is ReplyMode.DECISION:
        resolved = await resolve_decision_provider(services) if services else None
        if resolved is not None:
            dec_provider, dec_model = resolved
            mode_detail = (
                f"{_format_inline_code(dec_model)} "
                f"({_format_inline_code(dec_provider.name)})"
            )
        else:
            mode_detail = "Unconfigured"
    else:
        mode_detail = _format_percent(config.get("reply_percent", 0))

    mentions_state = _state_label(bool(config.get("reply_to_mentions_replies")))
    if config.get("random_messages_enabled"):
        random_chance = _format_percent(config.get("random_messages_percent", 0))
        random_interval = _format_duration(RANDOM_MESSAGE_TASK_RETRY_SECONDS)
        random_text = f"**On** ({random_chance} every {random_interval})"
    else:
        random_text = "Off"

    embed.add_field(
        name="Replies",
        value=(
            f"Mode: {_format_inline_code(reply_mode.value)} · {mode_detail}\n"
            f"Mentions & replies: {mentions_state} · Random: {random_text}"
        ),
        inline=False,
    )

    backread = config.get("messages_backread", 0)
    message_word = "message" if backread == 1 else "messages"
    gap_text = _format_duration(config.get("messages_backread_seconds", 0))
    compaction_state = _state_label(bool(config.get("compaction_enabled", False)))
    memory_state = _state_label(bool(config.get("query_memories")))
    tools_text = _format_tools(config)

    embed.add_field(
        name="Context & Features",
        value=(
            f"History: {backread} {message_word} · {gap_text} gap · "
            f"Compaction: {compaction_state}\n"
            f"Memory: {memory_state} · Tools: {tools_text}"
        ),
        inline=False,
    )

    embed.add_field(
        name="Media",
        value=_format_media_lines(config),
        inline=False,
    )

    optin_state = _state_label(bool(config.get("optin_by_default")))
    forget_state = _state_label(bool(config.get("public_forget")))
    members_whitelist = config.get("members_whitelist") or []
    roles_whitelist = config.get("roles_whitelist") or []
    allowlist_lines: list[str] = []
    if members_whitelist or roles_whitelist:
        allowlist_lines.append("Trigger allowlist: **On**")
        if members_whitelist:
            members = _join_bounded(
                [f"<@{member_id}>" for member_id in members_whitelist],
                max_length=_MAX_ALLOWLIST_LINE_LENGTH,
            )
            allowlist_lines.append(f"Allowed members: {members}")
        if roles_whitelist:
            roles = _join_bounded(
                [f"<@&{role_id}>" for role_id in roles_whitelist],
                max_length=_MAX_ALLOWLIST_LINE_LENGTH,
            )
            allowlist_lines.append(f"Allowed roles: {roles}")
    else:
        allowlist_lines.append("Trigger allowlist: Off")

    removelist_regexes = config.get("removelist_regexes") or []
    regexes_num = len(removelist_regexes)
    if regexes_num:
        filters_text = f"{regexes_num} {'pattern' if regexes_num == 1 else 'patterns'}"
    else:
        filters_text = "None"
    ignore_regex = config.get("ignore_regex")
    ignore_text = (
        _format_inline_code(ignore_regex, max_length=_MAX_IGNORE_REGEX_LENGTH)
        if ignore_regex
        else "None"
    )

    access_lines = [
        f"Opt-in by default: {optin_state} · Public forget: {forget_state}",
        *allowlist_lines,
        f"Response filters: {filters_text} · Ignore regex: {ignore_text}",
    ]
    embed.add_field(
        name="Access & Filters",
        value="\n".join(access_lines),
        inline=False,
    )

    parameters_value = _format_parameters_field(
        config.get("parameters"), ctx.clean_prefix
    )
    if parameters_value is not None:
        embed.add_field(
            name="Custom Parameters",
            value=parameters_value,
            inline=False,
        )

    embed.set_footer(
        text=f"aiuser v{version} • Run {ctx.clean_prefix}help aiuser for commands"
    )
    return embed
