# ./.venv/bin/python -m pytest aiuser/tests/test_context_cache.py -q -s

import pytest
from discord.ext.test import backend

from aiuser.context.entry import MessageEntry
from aiuser.tests.conftest import find_message_index, find_system_prompt_index


@pytest.mark.asyncio
async def test_cached_tool_calls(
    bot,
    build_conversation,
    mock_services,
    test_channel,
    test_member,
    mock_create_response,
    fake_llm,
):
    from openai.types.chat import ChatCompletionMessageToolCall
    from openai.types.chat.chat_completion_message_tool_call import Function

    # Simulate conversation history in channel:
    # 1. User asks about weather
    # 2. Bot responds (this is the message that will have cached tool calls)

    _ = backend.make_message("What is the weather in Paris?", test_member, test_channel)
    bot_msg = backend.make_message("It's rainy in Paris, 15°C.", bot.user, test_channel)

    # Create tool call entries that would have been cached during the simulated conversation
    tool_call = ChatCompletionMessageToolCall(
        id="call_paris_weather",
        type="function",
        function=Function(name="get_weather", arguments='{"location":"Paris"}'),
    )
    cached_entries = [
        MessageEntry(
            role="assistant",
            content="Checking the Paris forecast now.",
            tool_calls=[tool_call],
        ),
        MessageEntry(role="tool", content="Rainy, 15°C", tool_call_id=tool_call.id),
    ]

    mock_services.context_cache[("tool_calls", test_channel.id, bot_msg.id)] = (
        cached_entries
    )

    new_user_msg = backend.make_message(
        "Thanks! What about Tokyo?", test_member, test_channel
    )
    ctx = await bot.get_context(new_user_msg)

    thread = await build_conversation(init_message=new_user_msg)

    tool_call_entries = [m for m in thread.entries if m.tool_calls]
    tool_result_entries = [m for m in thread.entries if m.role == "tool"]

    assert len(tool_call_entries) >= 1
    assert len(tool_result_entries) >= 1

    # Verify message ordering in the thread (similar to test_history_builder)
    result = thread.to_chat_payload()

    user_ask_idx = find_message_index(result, "What is the weather in Paris?")
    cached_assistant_idx = find_message_index(
        result, "Checking the Paris forecast now."
    )
    bot_reply_idx = find_message_index(result, "It's rainy in Paris, 15°C.")
    tool_result_idx = find_message_index(result, "Rainy, 15°C")
    trigger_idx = find_message_index(result, "Thanks! What about Tokyo?")
    system_idx = find_system_prompt_index(result)

    # Find the tool call message with the correct Paris weather tool call ID
    paris_tool_call_id = "call_paris_weather"
    tool_call_idx = -1
    for i, m in enumerate(result):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            if any(tc["id"] == paris_tool_call_id for tc in m.get("tool_calls", [])):
                tool_call_idx = i
                break

    assert tool_call_idx != -1, (
        f"Tool call message with id '{paris_tool_call_id}' not found in thread"
    )
    assert cached_assistant_idx != -1, "Cached assistant content should be preserved"
    assert cached_assistant_idx == tool_call_idx, (
        "Cached assistant content and tool call should share the same assistant entry"
    )

    # Verify chronological order:
    # user ask -> cached assistant/tool call -> tool result -> bot reply -> system -> trigger
    assert (
        user_ask_idx
        < tool_call_idx
        < tool_result_idx
        < bot_reply_idx
        < system_idx
        < trigger_idx
    ), (
        f"Messages not in correct order: user_ask@{user_ask_idx}, cached_assistant/tool_call@{tool_call_idx}, tool_result@{tool_result_idx}, bot_reply@{bot_reply_idx}, system@{system_idx}, trigger@{trigger_idx}"
    )

    from unittest.mock import patch

    from aiuser.tests.conftest import text_step, tool_call_step

    tokyo_tool_call_id = "call_tokyo_weather"
    fake_llm(
        tool_call_step(
            "get_weather", '{"location":"Tokyo"}', call_id=tokyo_tool_call_id
        ),
        text_step("It's sunny in Tokyo, 20°C."),
    )

    await mock_services.config.guild(ctx.guild).function_calling.set(True)
    await mock_services.config.guild(ctx.guild).function_calling_functions.set(
        ["get_weather"]
    )

    with patch(
        "aiuser.functions.weather.query.get_weather",
        return_value="Sunny, 20°C",
    ):
        await mock_create_response(mock_services, ctx, conversation=thread)

    from discord.ext.test import get_message

    sent_msg = get_message()
    assert "Tokyo" in sent_msg.content

    cache_key = ("tool_calls", test_channel.id, sent_msg.id)
    assert cache_key in mock_services.context_cache
    cached_new = mock_services.context_cache[cache_key]

    assert any(
        m.role == "assistant"
        and m.tool_calls
        and m.tool_calls[0].id == tokyo_tool_call_id
        for m in cached_new
    )  # initial tool call
    assert any(
        m.role == "tool" and m.tool_call_id == tokyo_tool_call_id for m in cached_new
    )  # tool result
