# ./.venv/bin/python -m pytest aiuser/tests/test_tool_call_cache.py -q -s

import pytest
from discord.ext.test import backend

from aiuser.context.entry import MessageEntry


@pytest.mark.asyncio
async def test_cached_tool_calls(
    bot,
    mock_messages_thread,
    mock_cog,
    test_channel,
    test_member,
    mock_create_response,
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
        MessageEntry(role="assistant", content="", tool_calls=[tool_call]),
        MessageEntry(role="tool", content="Rainy, 15°C", tool_call_id=tool_call.id),
    ]

    mock_cog.cached_tool_calls[(test_channel.id, bot_msg.id)] = cached_entries

    new_user_msg = backend.make_message(
        "Thanks! What about Tokyo?", test_member, test_channel
    )
    ctx = await bot.get_context(new_user_msg)

    thread = await mock_messages_thread(init_message=new_user_msg)

    tool_call_entries = [m for m in thread.messages if m.tool_calls]
    tool_result_entries = [m for m in thread.messages if m.role == "tool"]

    assert len(tool_call_entries) >= 1
    assert len(tool_result_entries) >= 1

    from unittest.mock import AsyncMock, MagicMock, patch

    from openai.types.chat import (
        ChatCompletion,
        ChatCompletionMessage,
    )
    from openai.types.chat.chat_completion import Choice

    mock_cog.openai_client = MagicMock()

    tokyo_tool_call_id = "call_tokyo_weather"
    tokyo_tool_call = ChatCompletionMessageToolCall(
        id=tokyo_tool_call_id,
        type="function",
        function=Function(name="get_weather", arguments='{"location":"Tokyo"}'),
    )

    mock_response = ChatCompletion(
        id="chatcmpl-456",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", tool_calls=[tokyo_tool_call], content=None
                ),
                finish_reason="tool_calls",
            )
        ],
        created=1234567892,
        model="gpt-4",
        object="chat.completion",
    )

    final_response = ChatCompletion(
        id="chatcmpl-457",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content="It's sunny in Tokyo, 20°C.",
                    tool_calls=None,
                ),
                finish_reason="stop",
            )
        ],
        created=1234567893,
        model="gpt-4",
        object="chat.completion",
    )

    mock_cog.openai_client.chat.completions.create = AsyncMock(
        side_effect=[mock_response, final_response]
    )

    await mock_cog.config.guild(ctx.guild).function_calling.set(True)
    await mock_cog.config.guild(ctx.guild).function_calling_functions.set(
        ["get_weather"]
    )

    with patch(
        "aiuser.functions.weather.query.get_weather",
        return_value="Sunny, 20°C",
    ):
        await mock_create_response(mock_cog, ctx, messages_list=thread)

    from discord.ext.test import get_message

    sent_msg = get_message()
    assert "Tokyo" in sent_msg.content

    cache_key = (test_channel.id, sent_msg.id)
    assert cache_key in mock_cog.cached_tool_calls
    cached_new = mock_cog.cached_tool_calls[cache_key]

    assert any(
        m.role == "assistant"
        and m.tool_calls
        and m.tool_calls[0].id == tokyo_tool_call_id
        for m in cached_new
    )  # initial tool call
    assert any(
        m.role == "tool" and m.tool_call_id == tokyo_tool_call_id for m in cached_new
    )  # tool result
