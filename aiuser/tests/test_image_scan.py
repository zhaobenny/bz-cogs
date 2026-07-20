# ./.venv/bin/python -m pytest aiuser/tests/test_image_scan.py -q -s

import json

import pytest
from discord.ext.test import backend, get_message
from PIL import Image


@pytest.mark.asyncio
async def test_image_scan_message(
    bot,
    mock_services,
    build_conversation,
    test_guild,
    test_channel,
    test_member,
    mock_create_response,
    fake_llm,
    tmp_path,
):
    """
    Test that a message with an image attachment can be processed
    """
    from aiuser.tests.conftest import text_step

    # Create a temporary image file
    second_path = tmp_path / "test_image_2.png"
    tmp_path = tmp_path / "test_image.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(tmp_path, format="PNG")
    Image.new("RGB", (100, 100), color="blue").save(second_path, format="PNG")

    await mock_services.config.guild(test_guild).scan_images.set(True)
    await mock_services.config.guild(test_guild).max_image_size.set(1024 * 1024 * 10)

    attachment = backend.make_attachment(tmp_path, name="test_image.png")
    second_attachment = backend.make_attachment(second_path, name="test_image_2.png")
    # dpytest doesn't set content_type, monkeypatch it
    object.__setattr__(attachment, "content_type", "image/png")
    object.__setattr__(second_attachment, "content_type", "image/png")

    backend.make_message("earlier context", test_member, test_channel)
    user_message = backend.make_message(
        "look at this absolute 📸 masterpiece i found",
        test_member,
        test_channel,
        attachments=[attachment, second_attachment],
    )

    thread = await build_conversation(init_message=user_message)

    json_output = thread.to_chat_payload()
    serialized = json.dumps(json_output)

    assert len(json_output) > 0
    assert isinstance(serialized, str)
    image_parts = [
        part
        for message in json_output
        if isinstance(message["content"], list)
        for part in message["content"]
        if part.get("type") == "image_url"
    ]
    assert len(image_parts) == 2
    assert all(part["image_url"]["detail"] == "low" for part in image_parts)

    test_message_content = "holy, that's a massive W"
    fake_llm(text_step(test_message_content))

    ctx = await bot.get_context(user_message)

    await mock_create_response(mock_services, ctx, conversation=thread)

    sent_message = get_message()
    assert sent_message.content == test_message_content

    followup = backend.make_message(
        "what colors were those images?", test_member, test_channel
    )
    followup_thread = await build_conversation(init_message=followup)
    followup_image_parts = [
        part
        for message in followup_thread.to_chat_payload()
        if isinstance(message["content"], list)
        for part in message["content"]
        if part.get("type") == "image_url"
    ]
    assert len(followup_image_parts) == 2
