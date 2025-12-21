# ./.venv/bin/python -m pytest aiuser/tests/test_tool_call_cache.py -q -s

import pytest
from discord.ext.test import backend

from aiuser.context.entry import MessageEntry

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a location",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
    },
}


@pytest.mark.asyncio
async def test_cached_tool_calls(bot, openai_client, mock_messages_thread, mock_cog):
    """Full flow: cached tool calls are injected via HistoryBuilder and API accepts the result."""
    import discord.ext.test as dpytest
    from openai.types.chat import ChatCompletionMessageToolCall
    from openai.types.chat.chat_completion_message_tool_call import Function

    cfg = dpytest.get_config()
    channel = cfg.channels[0]
    member = cfg.members[0]
    await mock_cog.config.guild(cfg.guilds[0]).optin_by_default.set(True)

    # Simulate conversation history in channel:
    # 1. User asks about weather
    # 2. Bot responds (this is the message that will have cached tool calls)
    _ = backend.make_message("What is the weather in Paris?", member, channel)
    bot_msg = backend.make_message("It's rainy in Paris, 15°C.", bot.user, channel)

    # Create tool call entries that would have been cached during the original response
    tool_call = ChatCompletionMessageToolCall(
        id="call_paris_weather",
        type="function",
        function=Function(name="get_weather", arguments='{"location":"Paris"}'),
    )
    cached_entries = [
        MessageEntry(role="assistant", content="", tool_calls=[tool_call]),
        MessageEntry(role="tool", content="Rainy, 15°C", tool_call_id=tool_call.id),
    ]

    # Cache the tool calls keyed by (channel.id, bot_message.id)
    mock_cog.cached_tool_calls[(channel.id, bot_msg.id)] = cached_entries

    # Create a new user message (the "init message" for new conversation)
    new_user_msg = backend.make_message("Thanks! What about Tokyo?", member, channel)

    # Create thread using the new message as init, with history=True to trigger add_history
    thread = await mock_messages_thread(init_message=new_user_msg)

    # Verify tool calls were injected by HistoryBuilder
    # Check thread.messages directly since they contain the actual objects
    tool_call_entries = [m for m in thread.messages if m.tool_calls]
    tool_result_entries = [m for m in thread.messages if m.role == "tool"]

    assert len(tool_call_entries) >= 1, "Should have injected tool call message"
    assert len(tool_result_entries) >= 1, "Should have injected tool result message"
    assert tool_call_entries[0].tool_calls[0].id == "call_paris_weather"
    assert tool_result_entries[0].tool_call_id == "call_paris_weather"

    json_messages = thread.get_json()

    response = await openai_client.chat.completions.create(
        model="openai/gpt-4.1-nano", messages=json_messages, tools=[WEATHER_TOOL]
    )
    assert response.choices[0].message.content or response.choices[0].message.tool_calls

    await openai_client.close()
