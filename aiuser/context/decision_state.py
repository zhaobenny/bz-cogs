from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord
from redbot.core import commands

from aiuser.config.constants import DECISION_CONTEXT_MAX_MESSAGES
from aiuser.context.history import select_history_window, should_include_message
from aiuser.utils.utilities import format_variables, mention_to_text

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices


def _compact_message_text(message: discord.Message) -> str:
    parts: list[str] = []
    text = mention_to_text(message).strip()
    if text:
        parts.append(text)
    if message.attachments:
        image_names = [
            a.filename
            for a in message.attachments
            if (a.content_type or "").startswith("image/")
        ]
        other_names = [
            a.filename
            for a in message.attachments
            if not (a.content_type or "").startswith("image/")
        ]
        if image_names:
            parts.append(f"[Images: {', '.join(image_names)}]")
        if other_names:
            parts.append(f"[Attachments: {', '.join(other_names)}]")
    if message.stickers:
        sticker_names = ", ".join(s.name for s in message.stickers)
        parts.append(f"[Stickers: {sticker_names}]")
    return " ".join(parts)


def _format_message_record(
    message: discord.Message,
    *,
    bot_id: int,
    now: datetime,
) -> dict[str, Any] | None:
    text = _compact_message_text(message)
    if not text:
        return None

    created_at = message.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_seconds = max(0, int((now - created_at).total_seconds()))

    record: dict[str, Any] = {
        "author": message.author.display_name,
        "is_self": message.author.id == bot_id,
        "age_seconds": age_seconds,
        "text": text,
    }
    ref = message.reference
    if (
        ref
        and isinstance(ref.resolved, discord.Message)
        and ref.resolved.author.id == bot_id
    ):
        record["reply_to_self"] = True
    if any(user.id == bot_id for user in message.mentions):
        record["discord_mentions_self"] = True
    return record


async def build_decision_state(
    services: AIUserServices,
    ctx: commands.Context,
    *,
    max_messages: int = DECISION_CONTEXT_MAX_MESSAGES,
    seconds_since_bot_reply: float | None = None,
) -> dict[str, Any]:
    """Build a lightweight, privacy-filtered structured state for decision models.

    Reuses the same consent, allowlist, ignore-regex, and compaction/forget
    boundaries as :class:`ConversationAssembler`, without downloading media,
    transcribing audio, querying memories, or sending consent embeds.
    """
    guild = ctx.guild
    init_message = ctx.message
    bot_id = services.bot.user.id
    optin_by_default = await services.config.guild(guild).optin_by_default()
    history = await select_history_window(
        services,
        guild,
        init_message,
        max_messages=max_messages,
    )

    now = init_message.created_at
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    seen_ids: set[int] = set()
    recent_messages: list[dict[str, Any]] = []
    candidates: list[discord.Message] = list(history.messages)

    ref = init_message.reference
    if (
        ref
        and isinstance(ref.resolved, discord.Message)
        and all(m.id != ref.resolved.id for m in candidates)
    ):
        candidates.append(ref.resolved)
    candidates.append(init_message)

    for message in candidates:
        if not await should_include_message(
            services,
            guild.id,
            message,
            optin_by_default=optin_by_default,
            seen_ids=seen_ids,
        ):
            continue
        seen_ids.add(message.id)
        record = _format_message_record(message, bot_id=bot_id, now=now)
        if record is not None:
            recent_messages.append(record)

    bot_member = getattr(guild, "me", None)
    bot_name = (
        bot_member.display_name
        if bot_member is not None
        else services.bot.user.display_name
    )

    prompt = await services.resolver.resolve_prompt(
        guild=guild,
        channel=ctx.channel,
        member=init_message.author,
    )
    formatted_prompt = (await format_variables(ctx, prompt, services)).strip()

    state: dict[str, Any] = {
        "self_name": bot_name,
        "channel": getattr(ctx.channel, "name", str(ctx.channel.id)),
        "seconds_since_self_last_spoke": (
            int(seconds_since_bot_reply)
            if seconds_since_bot_reply is not None
            else None
        ),
        "recent_messages": recent_messages,
    }
    if formatted_prompt:
        state["self_persona"] = formatted_prompt
    if history.summary:
        state["conversation_summary"] = history.summary
    return state
