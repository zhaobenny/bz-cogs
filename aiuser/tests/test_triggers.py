from types import SimpleNamespace
from unittest.mock import patch

import pytest
from discord.ext.test import backend

from aiuser.core.handlers import get_percentage
from aiuser.core.triggers import (
    is_always_reply_on_words_triggered,
    is_in_conversation,
)
from aiuser.core.validators import (
    check_message_content,
    check_user_status,
    is_bot_mentioned_or_replied,
)


async def _is_conversation_reply_enabled(
    bot, mock_cog, test_channel, test_member, text
):
    """Create a recent bot message + user trigger, then evaluate conversation follow-up."""
    _ = backend.make_message("recent bot message", bot.user, test_channel)
    trigger = backend.make_message(text, test_member, test_channel)
    ctx = await bot.get_context(trigger)
    with patch("aiuser.core.triggers.random.random", return_value=0.5):
        return await is_in_conversation(mock_cog, ctx)


@pytest.mark.asyncio
async def test_conversation_reply_hierarchy_percent(
    bot,
    mock_cog,
    test_guild,
    test_channel,
    test_member,
):
    """Higher-specificity percent settings should override broader levels."""
    role = backend.make_role("ConversationTester", test_guild)
    backend.update_member(test_member, roles=[role])

    # Register role config so it appears in config.all_roles()
    await mock_cog.config.role(role).conversation_reply_percent.set(None)
    await mock_cog.config.role(role).conversation_reply_time.set(None)

    # Baseline via guild: should pass (0.9 > patched random 0.5)
    await mock_cog.config.guild(test_guild).conversation_reply_percent.set(0.9)
    await mock_cog.config.guild(test_guild).conversation_reply_time.set(300)

    # Clear narrower custom values
    await mock_cog.config.channel(test_channel).conversation_reply_percent.set(None)
    await mock_cog.config.member(test_member).conversation_reply_percent.set(None)
    await mock_cog.config.role(role).conversation_reply_percent.set(None)

    assert (
        await _is_conversation_reply_enabled(
            bot, mock_cog, test_channel, test_member, "guild baseline"
        )
        is True
    )

    # Channel overrides guild
    await mock_cog.config.channel(test_channel).conversation_reply_percent.set(0.0)
    assert (
        await _is_conversation_reply_enabled(
            bot, mock_cog, test_channel, test_member, "channel override"
        )
        is False
    )

    # Role overrides channel
    await mock_cog.config.role(role).conversation_reply_percent.set(0.9)
    assert (
        await _is_conversation_reply_enabled(
            bot, mock_cog, test_channel, test_member, "role override"
        )
        is True
    )

    # Member overrides role
    await mock_cog.config.member(test_member).conversation_reply_percent.set(0.0)
    assert (
        await _is_conversation_reply_enabled(
            bot, mock_cog, test_channel, test_member, "member override"
        )
        is False
    )


@pytest.mark.asyncio
async def test_conversation_reply_hierarchy_time(
    bot,
    mock_cog,
    test_guild,
    test_channel,
    test_member,
):
    """Higher-specificity time settings should override broader levels."""
    role = backend.make_role("ConversationTimer", test_guild)
    backend.update_member(test_member, roles=[role])

    # Register role config so it appears in config.all_roles()
    await mock_cog.config.role(role).conversation_reply_percent.set(None)
    await mock_cog.config.role(role).conversation_reply_time.set(None)

    # Percent always allows, so time window controls behavior
    await mock_cog.config.guild(test_guild).conversation_reply_percent.set(0.9)
    await mock_cog.config.guild(test_guild).conversation_reply_time.set(300)

    # Clear narrower custom values
    await mock_cog.config.channel(test_channel).conversation_reply_time.set(None)
    await mock_cog.config.member(test_member).conversation_reply_time.set(None)
    await mock_cog.config.role(role).conversation_reply_time.set(None)

    assert (
        await _is_conversation_reply_enabled(
            bot, mock_cog, test_channel, test_member, "guild time baseline"
        )
        is True
    )

    # Channel overrides guild (0 disables conversation continuation)
    await mock_cog.config.channel(test_channel).conversation_reply_time.set(0)
    assert (
        await _is_conversation_reply_enabled(
            bot, mock_cog, test_channel, test_member, "channel time override"
        )
        is False
    )

    # Role overrides channel
    await mock_cog.config.role(role).conversation_reply_time.set(300)
    assert (
        await _is_conversation_reply_enabled(
            bot, mock_cog, test_channel, test_member, "role time override"
        )
        is True
    )

    # Member overrides role
    await mock_cog.config.member(test_member).conversation_reply_time.set(0)
    assert (
        await _is_conversation_reply_enabled(
            bot, mock_cog, test_channel, test_member, "member time override"
        )
        is False
    )


@pytest.mark.asyncio
async def test_trigger_words_hierarchy(
    bot,
    mock_cog,
    test_guild,
    test_channel,
    test_member,
):
    role = backend.make_role("TriggerWordsRole", test_guild)
    backend.update_member(test_member, roles=[role])

    await mock_cog.config.role(role).always_reply_on_words.set(None)
    await mock_cog.config.channel(test_channel).always_reply_on_words.set(None)
    await mock_cog.config.member(test_member).always_reply_on_words.set(None)

    await mock_cog.config.guild(test_guild).always_reply_on_words.set(["guildword"])

    msg = backend.make_message("hello guildword", test_member, test_channel)
    ctx = await bot.get_context(msg)
    assert await is_always_reply_on_words_triggered(mock_cog, ctx) is True

    await mock_cog.config.channel(test_channel).always_reply_on_words.set(
        ["channelword"]
    )
    msg = backend.make_message("hello guildword", test_member, test_channel)
    ctx = await bot.get_context(msg)
    assert await is_always_reply_on_words_triggered(mock_cog, ctx) is False
    msg = backend.make_message("hello channelword", test_member, test_channel)
    ctx = await bot.get_context(msg)
    assert await is_always_reply_on_words_triggered(mock_cog, ctx) is True

    await mock_cog.config.role(role).always_reply_on_words.set(["roleword"])
    msg = backend.make_message("hello channelword", test_member, test_channel)
    ctx = await bot.get_context(msg)
    assert await is_always_reply_on_words_triggered(mock_cog, ctx) is False
    msg = backend.make_message("hello roleword", test_member, test_channel)
    ctx = await bot.get_context(msg)
    assert await is_always_reply_on_words_triggered(mock_cog, ctx) is True

    await mock_cog.config.member(test_member).always_reply_on_words.set(["memberword"])
    msg = backend.make_message("hello roleword", test_member, test_channel)
    ctx = await bot.get_context(msg)
    assert await is_always_reply_on_words_triggered(mock_cog, ctx) is False
    msg = backend.make_message("hello memberword", test_member, test_channel)
    ctx = await bot.get_context(msg)
    assert await is_always_reply_on_words_triggered(mock_cog, ctx) is True


@pytest.mark.asyncio
async def test_trigger_words_empty_list_blocks_inherited_words(
    bot,
    mock_cog,
    test_guild,
    test_channel,
    test_member,
):
    """Explicit empty list override should block inherited trigger words."""
    await mock_cog.config.guild(test_guild).always_reply_on_words.set(["guildword"])
    await mock_cog.config.channel(test_channel).always_reply_on_words.set([])

    msg = backend.make_message("hello guildword", test_member, test_channel)
    ctx = await bot.get_context(msg)
    assert await is_always_reply_on_words_triggered(mock_cog, ctx) is False


@pytest.mark.asyncio
async def test_conversation_reply_uses_highest_role_override(
    bot,
    mock_cog,
    test_guild,
    test_channel,
    test_member,
):
    """Conversation follow-up should use the highest-role override."""
    low_role = backend.make_role("ConversationLow", test_guild)
    high_role = backend.make_role("ConversationHigh", test_guild)
    low_role.position = 1
    high_role.position = 10
    backend.update_member(test_member, roles=[low_role, high_role])

    await mock_cog.config.guild(test_guild).conversation_reply_percent.set(0.9)
    await mock_cog.config.guild(test_guild).conversation_reply_time.set(300)
    await mock_cog.config.channel(test_channel).conversation_reply_percent.set(None)
    await mock_cog.config.member(test_member).conversation_reply_percent.set(None)

    await mock_cog.config.role(low_role).conversation_reply_percent.set(0.9)
    await mock_cog.config.role(low_role).conversation_reply_time.set(None)
    await mock_cog.config.role(high_role).conversation_reply_percent.set(0.0)
    await mock_cog.config.role(high_role).conversation_reply_time.set(None)

    assert (
        await _is_conversation_reply_enabled(
            bot, mock_cog, test_channel, test_member, "highest role percent override"
        )
        is False
    )


@pytest.mark.asyncio
async def test_min_length_hierarchy_in_validator(
    bot,
    mock_cog,
    test_guild,
    test_channel,
    test_member,
):
    role = backend.make_role("MinLengthRole", test_guild)
    backend.update_member(test_member, roles=[role])

    await mock_cog.config.role(role).messages_min_length.set(None)
    await mock_cog.config.channel(test_channel).messages_min_length.set(None)
    await mock_cog.config.member(test_member).messages_min_length.set(None)

    await mock_cog.config.guild(test_guild).messages_min_length.set(5)

    msg = backend.make_message("hey", test_member, test_channel)
    ctx = await bot.get_context(msg)
    ok, _ = await check_message_content(mock_cog, ctx)
    assert ok is False

    await mock_cog.config.channel(test_channel).messages_min_length.set(2)
    ok, _ = await check_message_content(mock_cog, ctx)
    assert ok is True

    await mock_cog.config.role(role).messages_min_length.set(6)
    ok, _ = await check_message_content(mock_cog, ctx)
    assert ok is False

    await mock_cog.config.member(test_member).messages_min_length.set(1)
    ok, _ = await check_message_content(mock_cog, ctx)
    assert ok is True


@pytest.mark.asyncio
async def test_reply_to_mentions_hierarchy(
    bot,
    mock_cog,
    test_guild,
    test_channel,
    test_member,
):
    role = backend.make_role("MentionsRole", test_guild)
    backend.update_member(test_member, roles=[role])

    await mock_cog.config.role(role).reply_to_mentions_replies.set(None)
    await mock_cog.config.channel(test_channel).reply_to_mentions_replies.set(None)
    await mock_cog.config.member(test_member).reply_to_mentions_replies.set(None)

    await mock_cog.config.guild(test_guild).reply_to_mentions_replies.set(True)

    msg = backend.make_message(f"<@{bot.user.id}> hi", test_member, test_channel)
    assert await is_bot_mentioned_or_replied(mock_cog, msg) is True

    await mock_cog.config.channel(test_channel).reply_to_mentions_replies.set(False)
    msg = backend.make_message(f"<@{bot.user.id}> hi", test_member, test_channel)
    assert await is_bot_mentioned_or_replied(mock_cog, msg) is False

    await mock_cog.config.role(role).reply_to_mentions_replies.set(True)
    msg = backend.make_message(f"<@{bot.user.id}> hi", test_member, test_channel)
    assert await is_bot_mentioned_or_replied(mock_cog, msg) is True

    await mock_cog.config.member(test_member).reply_to_mentions_replies.set(False)
    msg = backend.make_message(f"<@{bot.user.id}> hi", test_member, test_channel)
    assert await is_bot_mentioned_or_replied(mock_cog, msg) is False


@pytest.mark.asyncio
async def test_reply_to_mentions_uses_highest_role_override(
    bot,
    mock_cog,
    test_guild,
    test_channel,
    test_member,
):
    """Mention/reply trigger should honor highest-role boolean override."""
    low_role = backend.make_role("MentionsLow", test_guild)
    high_role = backend.make_role("MentionsHigh", test_guild)
    low_role.position = 1
    high_role.position = 10
    backend.update_member(test_member, roles=[low_role, high_role])

    await mock_cog.config.guild(test_guild).reply_to_mentions_replies.set(True)
    await mock_cog.config.channel(test_channel).reply_to_mentions_replies.set(None)
    await mock_cog.config.member(test_member).reply_to_mentions_replies.set(None)
    await mock_cog.config.role(low_role).reply_to_mentions_replies.set(True)
    await mock_cog.config.role(high_role).reply_to_mentions_replies.set(False)

    msg = backend.make_message(f"<@{bot.user.id}> hi", test_member, test_channel)
    assert await is_bot_mentioned_or_replied(mock_cog, msg) is False


@pytest.mark.asyncio
async def test_reply_percent_uses_highest_role_override(
    bot,
    mock_cog,
    test_guild,
    test_channel,
    test_member,
):
    """Main reply percentage lookup should use the highest-role override."""
    low_role = backend.make_role("PercentLow", test_guild)
    high_role = backend.make_role("PercentHigh", test_guild)
    low_role.position = 1
    high_role.position = 10
    backend.update_member(test_member, roles=[low_role, high_role])

    await mock_cog.config.guild(test_guild).reply_percent.set(0.9)
    await mock_cog.config.channel(test_channel).reply_percent.set(None)
    await mock_cog.config.member(test_member).reply_percent.set(None)
    await mock_cog.config.role(low_role).reply_percent.set(0.9)
    await mock_cog.config.role(high_role).reply_percent.set(0.0)

    msg = backend.make_message("hello", test_member, test_channel)
    ctx = await bot.get_context(msg)
    assert await get_percentage(mock_cog, ctx) == 0.0


@pytest.mark.asyncio
async def test_reply_to_webhooks_channel_override_in_validator(
    mock_cog,
    test_guild,
    test_channel,
):
    await mock_cog.config.guild(test_guild).reply_to_webhooks.set(True)
    await mock_cog.config.channel(test_channel).reply_to_webhooks.set(None)

    webhook_like_ctx = SimpleNamespace(
        guild=test_guild,
        channel=test_channel,
        interaction=None,
        message=SimpleNamespace(webhook_id=123456),
        author=SimpleNamespace(bot=False, id=999999),
    )

    ok, _ = await check_user_status(mock_cog, webhook_like_ctx)
    assert ok is True

    await mock_cog.config.channel(test_channel).reply_to_webhooks.set(False)
    ok, _ = await check_user_status(mock_cog, webhook_like_ctx)
    assert ok is False
