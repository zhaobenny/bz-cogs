# ./.venv/bin/python -m pytest aiuser/tests/test_image_scan.py -q -s

import json
import os
import tempfile
from pathlib import Path

import discord.ext.test as dpytest
import pytest
from discord.ext.test import backend
from PIL import Image


@pytest.mark.asyncio
async def test_image_scan_message(bot, mock_cog, mock_messages_thread):
    """
    Test that a message with an image attachment can be processed
    """
    # Create a temporary image file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img = Image.new("RGB", (100, 100), color="red")
        img.save(tmp, format="PNG")
        tmp_path = tmp.name

    try:
        # Enable image scanning in config
        cfg = dpytest.get_config()
        guild = cfg.guilds[0]
        await mock_cog.config.guild(guild).scan_images.set(True)
        await mock_cog.config.guild(guild).max_image_size.set(1024 * 1024 * 10)
        await mock_cog.config.guild(guild).optin_by_default.set(True)

        # Create attachment using dpytest
        attachment = backend.make_attachment(Path(tmp_path), name="test_image.png")
        # dpytest doesn't set content_type, so we need to monkeypatch it
        # Attachment is a frozen dataclass, so we use object.__setattr__
        object.__setattr__(attachment, "content_type", "image/png")

        # Create message with attachment
        channel = cfg.channels[0]
        member = cfg.members[0]
        message = backend.make_message(
            "Check out this image!", member, channel, attachments=[attachment]
        )

        # Create MessagesThread and add the message
        thread = await mock_messages_thread(init_message=message)

        # Add the message containing the image
        await thread.add_msg(message)

        # Verify the message can be serialized to JSON
        json_output = thread.get_json()
        serialized = json.dumps(json_output)
        # Basic assertions
        assert len(json_output) > 0
        assert isinstance(serialized, str)

        # TODO: put live api call here for complete testing

    finally:
        # Cleanup temp file
        os.unlink(tmp_path)
