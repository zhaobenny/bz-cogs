from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from discord.ext.test import backend

from aiuser.mcp.access import access_rule, allows_tool
from aiuser.mcp.access_view import MCPAccessView, MCPPanelLauncher
from aiuser.mcp.client import MCPOAuthRequired
from aiuser.mcp.manager import MCPManager
from aiuser.mcp.setup_view import MCPRemoveModal, MCPServerModal, MCPSetupView
from aiuser.mcp.tool_call import MCPToolCall
from aiuser.response.pipeline import LLMPipeline
from aiuser.tests.conftest import text_step, tool_call_step


def test_mcp_rule_precedence():
    member = SimpleNamespace(id=10, roles=[SimpleNamespace(id=20)])
    by_role = {**access_rule(), "roles": [20]}
    by_member = {**access_rule(), "members": [10]}
    policy = {
        "default": by_role,
        "tools": {
            "denied": access_rule(),
            "everyone": access_rule(everyone=True),
            "member": by_member,
        },
    }
    assert allows_tool({}, "new_tool", None)
    assert allows_tool(policy, "new_tool", member)
    assert not allows_tool(policy, "new_tool", None)
    assert not allows_tool(policy, "denied", member)
    assert allows_tool(policy, "everyone", None)
    assert allows_tool(policy, "member", member)


@pytest.mark.asyncio
async def test_access_panel_saves_and_clears_overrides(bot, redbot_config, test_guild):
    manager = MCPManager(bot, redbot_config, "test")
    await redbot_config.mcp_servers.set({"example": {"url": "https://example.com/mcp"}})
    panel = MCPAccessView(
        manager, test_guild, 10, "example", "https://example.com/mcp", "lookup"
    )
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock()), edit_original_response=AsyncMock()
    )
    config = redbot_config.guild(test_guild).mcp_tool_access
    await panel.embed()
    assert panel.children == [panel.audience]
    panel.audience._values = ["specific"]
    await panel.audience.callback(interaction)
    assert panel.members in panel.children and panel.roles in panel.children
    assert await config() == {}

    panel.members._values = [SimpleNamespace(id=10)]
    panel.roles._values = [SimpleNamespace(id=20)]
    await panel.members.callback(interaction)
    await panel.roles.callback(interaction)
    assert await config() == {}
    await panel.apply.callback(interaction)
    assert (await config())["example"]["tools"]["lookup"] == {
        "everyone": False,
        "members": [10],
        "roles": [20],
    }
    panel.audience._values = ["inherit"]
    await panel.audience.callback(interaction)
    assert "lookup" in (await config())["example"]["tools"]
    await panel.apply.callback(interaction)
    assert "lookup" not in (await config())["example"]["tools"]


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke_during_response", [False, True])
async def test_mcp_permissions_during_model_tool_round(
    bot,
    mock_services,
    build_conversation,
    test_guild,
    test_channel,
    test_member,
    fake_llm,
    revoke_during_response,
):
    config = mock_services.config
    manager = mock_services.mcp = MCPManager(bot, config, "test")
    await config.mcp_servers.set({"example": {"url": "https://example.com/mcp"}})
    guild_config = config.guild(test_guild)
    await guild_config.mcp_enabled_servers.set(["example"])
    await guild_config.function_calling.set(True)
    await guild_config.function_calling_functions.set([])
    await guild_config.mcp_tool_access.set(
        {
            "example": {
                "default": access_rule(),
                "tools": {"lookup": {**access_rule(), "members": [test_member.id]}},
            }
        }
    )
    client = SimpleNamespace(
        call_tool=AsyncMock(
            return_value={"content": [{"type": "text", "text": "MCP result"}]}
        )
    )
    lookup = MCPToolCall(client, "example", {"name": "lookup", "inputSchema": {}})
    blocked = MCPToolCall(client, "example", {"name": "blocked", "inputSchema": {}})
    manager.tools_for_mcp_server = AsyncMock(return_value=[lookup, blocked])
    provider = fake_llm(tool_call_step(lookup.function_name, "{}"), text_step("done"))
    create_chat_step = provider.create_chat_step

    async def respond(*args):
        if revoke_during_response:
            await guild_config.mcp_tool_access.set(
                {"example": {"default": access_rule()}}
            )
        return await create_chat_step(*args)

    provider.create_chat_step = respond
    message = backend.make_message("lookup please", test_member, test_channel)
    ctx = await bot.get_context(message)
    conversation = await build_conversation(init_message=message)
    result = await LLMPipeline(mock_services, ctx, conversation).run()

    offered = provider.calls[0][2]["tools"]
    assert [tool["function"]["name"] for tool in offered] == [lookup.function_name]
    if revoke_during_response:
        client.call_tool.assert_not_awaited()
    else:
        client.call_tool.assert_awaited_once_with("lookup", {})
    assert result.completion == "done"
    assert result.tool_call_entries == []


@pytest.mark.asyncio
async def test_setup_panel_add_enable_and_remove(bot, redbot_config, test_guild):
    manager = MCPManager(bot, redbot_config, "test")
    bot.get_shared_api_tokens = AsyncMock(return_value={})
    bot.remove_shared_api_tokens = AsyncMock()
    manager.tools_for_mcp_server = AsyncMock(return_value=[])
    view = MCPSetupView(manager, test_guild, 10)
    launcher = MCPPanelLauncher(view, "Open MCP setup")
    interaction = SimpleNamespace(
        response=SimpleNamespace(
            defer=AsyncMock(), send_message=AsyncMock(), edit_message=AsyncMock()
        ),
        followup=SimpleNamespace(send=AsyncMock()),
        message=None,
        edit_original_response=AsyncMock(),
    )
    await launcher.open_panel.callback(interaction)
    assert interaction.response.send_message.await_args.kwargs["ephemeral"]
    assert view.children == [view.add]

    add = MCPServerModal(view)
    add.alias_input._value = "example"
    add.endpoint._value = "https://example.com/mcp"
    await add.on_submit(interaction)
    assert view.alias == "example"
    assert view.primary.label == "Review and enable"
    assert view.previous not in view.children
    assert view.next_page not in view.children

    await view.primary.callback(interaction)
    assert await redbot_config.guild(test_guild).mcp_enabled_servers() == []
    review = interaction.edit_original_response.await_args.kwargs["view"]
    await review.enable.callback(interaction)
    assert view.primary.label == "Disable here"
    assert await redbot_config.guild(test_guild).mcp_enabled_servers() == ["example"]

    edit = MCPServerModal(view, "example", "https://example.com/mcp")
    edit.endpoint._value = "https://example.com/mcp-v2"
    await edit.on_submit(interaction)
    assert (await redbot_config.mcp_servers())["example"]["url"].endswith("mcp-v2")

    manager.tools_for_mcp_server = AsyncMock(
        side_effect=MCPOAuthRequired(challenge="Bearer")
    )
    await view.auth(interaction)
    auth_view = interaction.followup.send.await_args.kwargs["view"]
    assert auth_view.challenge == "Bearer"
    assert auth_view.url == "https://example.com/mcp-v2"

    manager.tools_for_mcp_server = AsyncMock(
        return_value=[SimpleNamespace(native_name="lookup")]
    )
    await view.tool_access.callback(interaction)
    access = interaction.edit_original_response.await_args.kwargs["view"]
    assert access.tool is None
    chooser = next(
        item
        for item in access.children
        if getattr(item, "label", None) == "Choose a tool"
    )
    await chooser.callback(interaction)
    picker = interaction.response.edit_message.await_args.kwargs["view"]
    await picker.open_rule(interaction, "lookup")
    assert interaction.response.edit_message.await_args.kwargs["view"].tool == "lookup"

    remove = MCPRemoveModal(view, "example")
    remove.confirmation._value = "example"
    await remove.on_submit(interaction)
    assert await redbot_config.mcp_servers() == {}
    assert await redbot_config.guild(test_guild).mcp_enabled_servers() == []
