# ./.venv/bin/python -m pytest aiuser/tests/test_history_builder.py -q -s

import pytest
from discord.ext.test import backend

from aiuser.tests.conftest import find_message_index, find_system_prompt_index


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


@pytest.mark.asyncio
async def test_prune_messages_on_over_limit(
    bot,
    mock_cog,
    mock_messages_thread,
    mock_create_response,
    test_channel,
    test_member,
):
    from unittest.mock import AsyncMock, MagicMock, patch

    from openai.types.chat import (
        ChatCompletion,
        ChatCompletionMessage,
        ChatCompletionMessageToolCall,
    )
    from openai.types.chat.chat_completion import Choice
    from openai.types.chat.chat_completion_message_tool_call import Function

    from aiuser.utils.utilities import encode_text_to_tokens

    _ = backend.make_message("yo", test_member, test_channel)
    _ = backend.make_message("What's the meaning to life?", test_member, test_channel)
    _ = backend.make_message("42", bot.user, test_channel)
    trigger = backend.make_message(
        "Okay smart guy, what's the weather in NYC?", test_member, test_channel
    )

    thread = await mock_messages_thread(init_message=trigger)

    thread_json = thread.get_json()
    prunable_tokens_1 = await encode_text_to_tokens(
        str(thread_json[0].get("content", ""))
    )
    prunable_tokens_2 = await encode_text_to_tokens(
        str(thread_json[1].get("content", ""))
    )
    thread.token_limit = thread.tokens - prunable_tokens_1 - prunable_tokens_2

    mock_cog.openai_client = MagicMock()

    tool_call = ChatCompletionMessageToolCall(
        id="call_prune_test",
        type="function",
        function=Function(name="get_weather", arguments='{"location":"NYC"}'),
    )

    tool_call_response = ChatCompletion(
        id="chatcmpl-tool",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", tool_calls=[tool_call], content=None
                ),
                finish_reason="tool_calls",
            )
        ],
        created=1234567891,
        model="gpt-4",
        object="chat.completion",
    )

    final_response = ChatCompletion(
        id="chatcmpl-final",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content="tool result response",
                    tool_calls=None,
                ),
                finish_reason="stop",
            )
        ],
        created=1234567892,
        model="gpt-4",
        object="chat.completion",
    )

    mock_cog.openai_client.chat.completions.create = AsyncMock(
        side_effect=[tool_call_response, final_response]
    )

    await mock_cog.config.guild(test_member.guild).function_calling.set(True)
    await mock_cog.config.guild(test_member.guild).function_calling_functions.set(
        ["get_weather"]
    )

    ctx = await bot.get_context(trigger)
    with patch(
        "aiuser.functions.weather.query.get_weather",
        return_value="Sunny, 25°C",
    ):
        await mock_create_response(mock_cog, ctx, messages_list=thread)

    result = thread.get_json()

    pruned_1_idx = find_message_index(result, "What's the meaning to life?")
    pruned_2_idx = find_message_index(result, "42")
    assert pruned_1_idx == -1, "First history message should be pruned"
    assert pruned_2_idx == -1, "Second history message should be pruned"

    system_idx = find_system_prompt_index(result)
    trigger_idx = find_message_index(
        result, "Okay smart guy, what's the weather in NYC?"
    )
    tool_result_idx = find_message_index(result, "Sunny, 25°C")

    assert system_idx != -1, "System prompt should be preserved"
    assert trigger_idx != -1, "Trigger message should be preserved"
    assert tool_result_idx != -1, "Tool result message should be present"
