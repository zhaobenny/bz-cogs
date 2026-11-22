# ./.venv/bin/python -m pytest aiuser/tests/test_pipeline.py -q -s

import pytest
from discord.ext.test import backend

from aiuser.functions import names
from aiuser.response.pipeline import LLMPipeline
from aiuser.tests.conftest import text_step, tool_call_step

RESPOND_ARGS = '{"reason": "still thinking", "respond": true}'
SUPPRESS_ARGS = '{"reason": "boring conversation", "respond": false}'


async def make_pipeline(
    bot, mock_services, build_conversation, test_member, test_channel
):
    message = backend.make_message("hey bot", test_member, test_channel)
    ctx = await bot.get_context(message)
    conversation = await build_conversation(init_message=message)
    return LLMPipeline(mock_services, ctx, conversation)


async def enable_noresponse_tool(mock_services, test_guild):
    await mock_services.config.guild(test_guild).function_calling.set(True)
    await mock_services.config.guild(test_guild).function_calling_functions.set(
        [names.DO_NOT_RESPOND]
    )


@pytest.mark.asyncio
async def test_tool_call_rounds_exhaustion(
    bot,
    mock_services,
    build_conversation,
    test_guild,
    test_channel,
    test_member,
    fake_llm,
):
    """Exhausting the round limit triggers one final request without tools."""
    await enable_noresponse_tool(mock_services, test_guild)
    await mock_services.config.guild(test_guild).function_calling_tool_call_rounds.set(
        2
    )

    fake = fake_llm(
        tool_call_step(names.DO_NOT_RESPOND, RESPOND_ARGS, call_id="call_r1"),
        tool_call_step(names.DO_NOT_RESPOND, RESPOND_ARGS, call_id="call_r2"),
        text_step("final answer"),
    )

    pipeline = await make_pipeline(
        bot, mock_services, build_conversation, test_member, test_channel
    )
    result = await pipeline.run()

    assert result.completion == "final answer"
    assert len(fake.calls) == 3
    assert "tools" in fake.calls[0][2]
    assert "tools" in fake.calls[1][2]
    assert "tools" not in fake.calls[2][2], "final request must go out without tools"


@pytest.mark.asyncio
async def test_suppress_response_breaks_loop(
    bot,
    mock_services,
    build_conversation,
    test_guild,
    test_channel,
    test_member,
    fake_llm,
):
    await enable_noresponse_tool(mock_services, test_guild)

    fake = fake_llm(tool_call_step(names.DO_NOT_RESPOND, SUPPRESS_ARGS))

    pipeline = await make_pipeline(
        bot, mock_services, build_conversation, test_member, test_channel
    )
    result = await pipeline.run()

    assert result.completion is None
    assert len(fake.calls) == 1, "loop must stop after the suppressing tool call"


@pytest.mark.asyncio
async def test_empty_step_breaks_loop(
    bot,
    mock_services,
    build_conversation,
    test_guild,
    test_channel,
    test_member,
    fake_llm,
):
    await enable_noresponse_tool(mock_services, test_guild)

    fake = fake_llm(text_step(None))

    pipeline = await make_pipeline(
        bot, mock_services, build_conversation, test_member, test_channel
    )
    result = await pipeline.run()

    assert result.completion is None
    assert len(fake.calls) == 1, "no content and no tool calls must end the loop"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("is_owner", "addresses_bot", "supports_tools", "disable_config_help"),
    [
        (True, True, True, False),
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
        (True, True, True, True),
    ],
)
async def test_config_help_is_available_only_in_supported_owner_chat(
    bot,
    mock_services,
    build_conversation,
    test_guild,
    test_channel,
    test_member,
    fake_llm,
    monkeypatch,
    is_owner,
    addresses_bot,
    supports_tools,
    disable_config_help,
):
    from dataclasses import replace

    from aiuser.config.model_info import get_model_info
    from aiuser.functions.config_help import ConfigHelpToolCall

    async def check_owner(author):
        assert author == test_member
        return is_owner

    monkeypatch.setattr(bot, "is_owner", check_owner)
    monkeypatch.setattr(
        "aiuser.response.pipeline.get_model_info",
        lambda model: replace(get_model_info(model), supports_tools=supports_tools),
    )
    message = backend.make_message("Why are you so chatty?", test_member, test_channel)
    if addresses_bot:
        message.mentions = [bot.user]
    ctx = await bot.get_context(message)
    conversation = await build_conversation(init_message=message)

    config = mock_services.config
    await config.guild(test_guild).channels_whitelist.set([test_channel.id])
    await config.guild(test_guild).reply_percent.set(0.1)
    await config.channel(test_channel).reply_percent.set(0.0)
    assert not await config.guild(test_guild).function_calling()
    assert await config.guild(test_guild).config_help_enabled()
    if disable_config_help:
        await config.guild(test_guild).config_help_enabled.set(False)

    tool_name = ConfigHelpToolCall.function_name
    fake = fake_llm(
        tool_call_step(tool_name, '{"topic": "replies"}'),
        text_step("Here are your reply settings."),
    )
    result = await LLMPipeline(mock_services, ctx, conversation).run()

    assert result.completion == "Here are your reply settings."
    assert result.tool_call_entries == []
    if is_owner and addresses_bot and supports_tools and not disable_config_help:
        assert fake.calls[0][2]["tools"][0]["function"]["name"] == tool_name
        assert '"reply_percent": {"value": 0.0, "scope": "channel"}' in str(
            fake.calls[1][1][-1]["content"]
        )
        assert '"installed_cog_source"' in str(fake.calls[1][1][-1]["content"])
    else:
        assert "tools" not in fake.calls[0][2]
        assert "Invalid tool call" in str(fake.calls[1][1][-1]["content"])
