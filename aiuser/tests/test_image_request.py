# ./.venv/bin/python -m pytest aiuser/tests/test_image_request.py -q -s


from unittest.mock import patch

import pytest
from discord.ext.test import backend, get_message


@pytest.mark.asyncio
async def test_image_request(
    bot,
    mock_cog,
    mock_messages_thread,
    test_guild,
    test_channel,
    test_member,
    mock_create_response,
):
    from unittest.mock import AsyncMock, MagicMock

    from openai.types.chat import (
        ChatCompletion,
        ChatCompletionMessage,
        ChatCompletionMessageToolCall,
    )
    from openai.types.chat.chat_completion import Choice
    from openai.types.chat.chat_completion_message_tool_call import Function

    # Set preprompt with variables
    preprompt_template = "Create a safe-for-work image requested by {authorname} watermarked with {botname} "
    await mock_cog.config.guild(test_guild).function_calling_image_preprompt.set(
        preprompt_template
    )

    # Enable function calling and specific tool
    await mock_cog.config.guild(test_guild).function_calling.set(True)
    await mock_cog.config.guild(test_guild).function_calling_functions.set(
        ["image_request"]
    )

    user_message = backend.make_message(
        "yo bot, make me a pic of a cat wearing sunglasses 😎",
        test_member,
        test_channel,
    )
    ctx = await bot.get_context(user_message)
    thread = await mock_messages_thread(init_message=user_message)

    mock_cog.openai_client = MagicMock()

    image_description = "a high-quality image of a fluffy orange cat wearing cool sunglasses, cinematic lighting"
    tool_call = ChatCompletionMessageToolCall(
        id="call_image_123",
        type="function",
        function=Function(
            name="image_request",
            arguments=f'{{"description": "{image_description}"}}',
        ),
    )

    mock_response = ChatCompletion(
        id="chatcmpl-123",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", tool_calls=[tool_call], content=None
                ),
                finish_reason="tool_calls",
            )
        ],
        created=1234567890,
        model="gpt-4",
        object="chat.completion",
    )

    final_response = ChatCompletion(
        id="chatcmpl-124",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content="Here's your cool cat! 🔥",
                    tool_calls=None,
                ),
                finish_reason="stop",
            )
        ],
        created=1234567891,
        model="gpt-4",
        object="chat.completion",
    )

    mock_cog.openai_client.chat.completions.create = AsyncMock(
        side_effect=[mock_response, final_response]
    )

    captured_descriptions = []

    # Mock the image provider to capture the description it receives
    async def mock_provider(description, request, endpoint):
        captured_descriptions.append(description)
        # Return minimal valid PNG bytes
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with (
        patch(
            "aiuser.functions.imagerequest.tool_call.PROVIDERS", {"mock": mock_provider}
        ),
        patch(
            "aiuser.functions.imagerequest.tool_call.detect_provider",
            return_value="mock",
        ),
    ):
        await mock_create_response(mock_cog, ctx, messages_list=thread)

    sent_message = get_message()
    assert sent_message.attachments
    assert sent_message.attachments[0].filename == "image.png"

    assert len(captured_descriptions) == 1
    final_description = captured_descriptions[0]

    assert "{authorname}" not in final_description
    assert "{botname}" not in final_description

    assert "Create a safe-for-work image" in final_description
    assert f"requested by {test_member.display_name}" in final_description
    assert "watermarked with" in final_description
    assert image_description in final_description
