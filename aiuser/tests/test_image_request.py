# ./.venv/bin/python -m pytest aiuser/tests/test_image_request.py -q -s

from unittest.mock import MagicMock, patch

import discord.ext.test as dpytest
import pytest
from discord.ext.test import backend


@pytest.mark.asyncio
async def test_image_request(bot, mock_cog, mock_messages_thread):
    from aiuser.functions.imagerequest.tool_call import ImageRequestToolCall
    from aiuser.response.llm_pipeline import LLMPipeline

    cfg = dpytest.get_config()
    guild = cfg.guilds[0]
    channel = cfg.channels[0]
    member = cfg.members[0]

    # Set preprompt with variables
    preprompt_template = "Create a safe-for-work image requested by {authorname} watermarked with {botname} "
    await mock_cog.config.guild(guild).function_calling_image_preprompt.set(
        preprompt_template
    )
    await mock_cog.config.guild(guild).optin_by_default.set(True)

    # Create message and context
    message = backend.make_message("Generate a cat image", member, channel)
    ctx = await bot.get_context(message)

    # Create real MessagesThread and LLMPipeline
    thread = await mock_messages_thread(init_message=message)

    # Only mock the openai_client on the cog
    mock_cog.openai_client = MagicMock()

    # Create real LLMPipeline
    request = LLMPipeline(mock_cog, ctx, thread)

    # Mock the image provider to capture the description it receives
    captured_descriptions = []

    async def mock_provider(description, request, endpoint):
        captured_descriptions.append(description)
        # Return minimal valid PNG bytes
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    # Patch the provider factory to use our mock
    with (
        patch(
            "aiuser.functions.imagerequest.tool_call.PROVIDERS", {"mock": mock_provider}
        ),
        patch(
            "aiuser.functions.imagerequest.tool_call.detect_provider",
            return_value="mock",
        ),
    ):
        tool = ImageRequestToolCall(config=mock_cog.config, ctx=ctx)
        result = await tool._handle(request, {"description": "a fluffy cat"})

    # Verify the tool succeeded
    assert result is not None
    assert len(request.files_to_send) == 1

    # Verify preprompt variables were substituted in the description
    assert len(captured_descriptions) == 1
    final_description = captured_descriptions[0]

    # Check that template variables were replaced with actual values
    assert "{authorname}" not in final_description
    assert "{botname}" not in final_description

    # Check for the text components
    assert "Create a safe-for-work image" in final_description
    assert f"requested by {member.display_name}" in final_description
    assert "watermarked with" in final_description
    assert "a fluffy cat" in final_description
