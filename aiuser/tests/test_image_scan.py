# ./.venv/bin/python -m pytest aiuser/tests/test_image_scan.py -q -s

import json

import pytest
from discord.ext.test import backend, get_message
from PIL import Image


@pytest.mark.asyncio
async def test_image_scan_message(
    bot,
    mock_cog,
    mock_messages_thread,
    test_guild,
    test_channel,
    test_member,
    mock_create_response,
    tmp_path,
):
    """
    Test that a message with an image attachment can be processed
    """
    from unittest.mock import AsyncMock, MagicMock

    from openai.types.chat import ChatCompletion, ChatCompletionMessage
    from openai.types.chat.chat_completion import Choice

    # Create a temporary image file
    tmp_path = tmp_path / "test_image.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(tmp_path, format="PNG")

    await mock_cog.config.guild(test_guild).scan_images.set(True)
    await mock_cog.config.guild(test_guild).max_image_size.set(1024 * 1024 * 10)

    attachment = backend.make_attachment(tmp_path, name="test_image.png")
    # dpytest doesn't set content_type, monkeypatch it
    object.__setattr__(attachment, "content_type", "image/png")

    user_message = backend.make_message(
        "look at this absolute 📸 masterpiece i found",
        test_member,
        test_channel,
        attachments=[attachment],
    )

    thread = await mock_messages_thread(init_message=user_message)

    json_output = thread.get_json()
    serialized = json.dumps(json_output)

    assert len(json_output) > 0
    assert isinstance(serialized, str)

    mock_cog.openai_client = MagicMock()

    test_message_content = "holy, that's a massive W"
    mock_response = ChatCompletion(
        id="chatcmpl-scan-123",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content=test_message_content,
                    tool_calls=None,
                ),
                finish_reason="stop",
            )
        ],
        created=1234567890,
        model="gpt-4",
        object="chat.completion",
    )

    mock_cog.openai_client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    ctx = await bot.get_context(user_message)

    await mock_create_response(mock_cog, ctx, messages_list=thread)

    sent_message = get_message()
    assert sent_message.content == test_message_content
