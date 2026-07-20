# ./.venv/bin/python -m pytest aiuser/tests/test_llm_provider.py -q -s

from unittest.mock import AsyncMock, MagicMock

import pytest
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import Function

from aiuser.providers.llm.openai_compatible.provider import OpenAICompatibleProvider


def make_completion(message: ChatCompletionMessage, finish_reason: str) -> ChatCompletion:
    return ChatCompletion(
        id="chatcmpl-test",
        choices=[Choice(index=0, message=message, finish_reason=finish_reason)],
        created=1234567890,
        model="gpt-4",
        object="chat.completion",
    )


@pytest.mark.asyncio
async def test_create_chat_step_translates_content():
    client = MagicMock()
    completion = make_completion(
        ChatCompletionMessage(role="assistant", content="hello", tool_calls=None),
        finish_reason="stop",
    )
    client.chat.completions.create = AsyncMock(return_value=completion)

    config = MagicMock()
    config.custom_openai_endpoint = AsyncMock(return_value=None)
    provider = OpenAICompatibleProvider(config, client)
    messages = [{"role": "user", "content": "hi"}]
    step = await provider.create_chat_step("gpt-4", messages, {"temperature": 0.5})

    client.chat.completions.create.assert_awaited_once_with(
        model="gpt-4", messages=messages, temperature=0.5
    )
    assert step.content == "hello"
    assert step.tool_calls == []
    assert step.assistant_extra_fields == {}
    assert step.finish_reason == "stop"


@pytest.mark.asyncio
async def test_create_chat_step_translates_tool_calls_and_extra_fields():
    tool_call = ChatCompletionMessageToolCall(
        id="call_1",
        type="function",
        function=Function(name="get_weather", arguments='{"location":"NYC"}'),
    )
    message = ChatCompletionMessage(
        role="assistant", content=None, tool_calls=[tool_call]
    )
    # openrouter-style extra field on the message, picked up via getattr
    message.reasoning = "checking the forecast"

    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=make_completion(message, finish_reason="tool_calls")
    )

    config = MagicMock()
    config.custom_openai_endpoint = AsyncMock(return_value=None)
    provider = OpenAICompatibleProvider(config, client)
    step = await provider.create_chat_step("gpt-4", [], {})

    assert step.content is None
    assert step.tool_calls == [tool_call]
    assert step.assistant_extra_fields == {"reasoning": "checking the forecast"}
    assert step.finish_reason == "tool_calls"
