# ./.venv/bin/python -m pytest aiuser/tests/test_history_builder.py -q -s

import pytest
from discord.ext.test import backend


def find_message_index(result, content_substring):
    """Find the index of a message containing the given substring."""
    for i, m in enumerate(result):
        if content_substring in str(m.get("content", "")):
            return i
    return -1


def find_system_prompt_index(result):
    """Find the index of the system prompt (contains persona/bot instructions)."""
    for i, m in enumerate(result):
        if m["role"] == "system" and "You are" in str(
            m.get("content", "")
        ):  # hack for checking system prompt
            return i
    return -1


@pytest.mark.asyncio
async def test_basic_history_order(
    bot,
    mock_messages_thread,
    test_channel,
    test_member,
):
    _ = backend.make_message("gm everyone ☀️", test_member, test_channel)
    _ = backend.make_message(
        "beep boop, anyone up for a hangout later?", bot.user, test_channel
    )
    trigger = backend.make_message(
        "i'm down, just finishing some work", test_member, test_channel
    )

    thread = await mock_messages_thread(init_message=trigger)
    result = thread.get_json()

    # Find message indices
    first_idx = find_message_index(result, "gm everyone ☀️")
    second_idx = find_message_index(result, "beep boop, anyone up for a hangout later?")
    third_idx = find_message_index(result, "i'm down, just finishing some work")
    system_idx = find_system_prompt_index(result)

    # Verify chronological order
    assert (
        first_idx < second_idx < system_idx < third_idx
    ), f"Messages not in chronological order: First@{first_idx}, Second@{second_idx}, System@{system_idx}, Third@{third_idx}"


@pytest.mark.asyncio
async def test_multi_user_conversation_order(
    bot,
    mock_messages_thread,
    test_channel,
    test_member,
):
    user_alice = backend.make_member(
        backend.make_user("Alice", "1001"), test_member.guild
    )
    user_bob = backend.make_member(backend.make_user("Bob", "1002"), test_member.guild)

    # Create interleaved conversation (not alternating user/bot)
    _ = backend.make_message(
        "hey guys! did you see the news??", user_alice, test_channel
    )
    _ = backend.make_message("yo Alice, what happened??", user_bob, test_channel)
    _ = backend.make_message("it's honestly wild frfr 💯", user_alice, test_channel)
    _ = backend.make_message("what the heck, beep boop", bot.user, test_channel)
    _ = backend.make_message("is it really that big of a deal?", user_bob, test_channel)
    trigger = backend.make_message(
        "honestly same, need more caffeine ☕", user_alice, test_channel
    )

    thread = await mock_messages_thread(init_message=trigger)
    result = thread.get_json()

    # Find message indices
    alice_hello = find_message_index(result, "hey guys! did you see the news??")
    bob_joins = find_message_index(result, "yo Alice, what happened??")
    alice_responds = find_message_index(result, "it's honestly wild frfr 💯")
    bot_responds = find_message_index(result, "what the heck, beep boop")
    bob_asks = find_message_index(result, "is it really that big of a deal?")
    trigger_idx = find_message_index(result, "honestly same, need more caffeine ☕")
    system_idx = find_system_prompt_index(result)

    # Verify chronological order
    assert (
        alice_hello
        < bob_joins
        < alice_responds
        < bot_responds
        < bob_asks
        < system_idx
        < trigger_idx
    ), "Multi-user messages not in chronological order"


@pytest.mark.asyncio
async def test_consecutive_user_messages_order(
    bot,
    mock_messages_thread,
    test_channel,
    test_member,
):
    user_alice = backend.make_member(
        backend.make_user("Alice", "2001"), test_member.guild
    )

    # Alice sends multiple messages in a row before bot responds
    _ = backend.make_message("gm", user_alice, test_channel)
    _ = backend.make_message("how is everyone today?", user_alice, test_channel)
    _ = backend.make_message("anyone doing anything fun?", user_alice, test_channel)
    _ = backend.make_message("No, I'm memory leaking", bot.user, test_channel)
    trigger = backend.make_message(
        "understandable have a nice day", user_alice, test_channel
    )

    thread = await mock_messages_thread(init_message=trigger)
    result = thread.get_json()

    # Find message indices
    msg1 = find_message_index(result, "gm")
    msg2 = find_message_index(result, "how is everyone today?")
    msg3 = find_message_index(result, "anyone doing anything fun?")
    bot_resp = find_message_index(result, "No, I'm memory leaking")
    trigger_idx = find_message_index(result, "understandable have a nice day")
    system_idx = find_system_prompt_index(result)

    # Verify order
    assert (
        msg1 < msg2 < msg3 < bot_resp < system_idx < trigger_idx
    ), "Consecutive user messages not in chronological order"


@pytest.mark.asyncio
async def test_optout_user_excluded(
    bot,
    mock_cog,
    mock_messages_thread,
    test_channel,
    test_member,
):
    """Test that opted-out users' messages are excluded from history."""
    optout_member = backend.make_member(
        backend.make_user("optout_user", "5678"), test_member.guild
    )

    await mock_cog.config.optout.set([optout_member.id])

    _ = backend.make_message("No one is listening", optout_member, test_channel)
    _ = backend.make_message("What are you yapping about?", test_member, test_channel)
    trigger = backend.make_message("Just chill.", test_member, test_channel)

    thread = await mock_messages_thread(init_message=trigger)
    result = thread.get_json()

    # Check by index - optout user's message should not be found
    optout_idx = find_message_index(result, "No one is listening")
    assert optout_idx == -1, "Optout user's message should not be in result"
