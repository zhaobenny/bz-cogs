from __future__ import annotations

import asyncio
import json
import logging
import re
from enum import Enum, auto
from typing import Any

import discord
from redbot.core import Config
from redbot.core.bot import Red

from aiuser.mcp.access import allows_tool
from aiuser.mcp.client import MCPClient, MCPError
from aiuser.mcp.oauth import MCPOAuth
from aiuser.mcp.tool_call import MCPToolCall

logger = logging.getLogger("red.bz_cogs.aiuser.mcp")


class ManagerPhase(Enum):
    OPEN = auto()
    CLOSING = auto()
    CLOSED = auto()


class MCPManager:
    def __init__(self, bot: Red, config: Config, version: str):
        self.phase = ManagerPhase.OPEN
        self.bot = bot
        self.config = config
        self.version = version
        self.oauth = MCPOAuth(bot)
        self._clients: dict[tuple[int, str], tuple[str, MCPClient]] = {}
        self._lock = asyncio.Lock()
        self._close_lock = asyncio.Lock()
        self._closing_clients: list[MCPClient] = []

    async def add_server(self, name: str, url: str):
        if not re.fullmatch(r"[a-z0-9_-]{1,32}", name):
            raise MCPError(
                "Server names must use 1-32 lowercase letters, numbers, `_`, or `-`."
            )
        server = {"url": url}
        async with self.config.mcp_servers() as servers:
            if name in servers:
                raise MCPError(f"MCP server `{name}` already exists.")
            servers[name] = server
        return server

    async def update_url(self, name: str, url: str):
        async with self.config.mcp_servers() as servers:
            if name not in servers:
                raise MCPError(f"Unknown MCP server `{name}`.")
            server = servers[name]
            if server["url"] == url:
                return server
            await self.oauth.forget(name)
            await self.bot.remove_shared_api_tokens(f"mcp_{name}", "token")
            server["url"] = url
        await self.invalidate_server(name)
        return server

    async def remove_server(self, name: str):
        async with self.config.mcp_servers() as servers:
            if name not in servers:
                raise MCPError(f"Unknown MCP server `{name}`.")
            await self.oauth.forget(name)
            await self.bot.remove_shared_api_tokens(f"mcp_{name}", "token")
            for guild_id, data in (await self.config.all_guilds()).items():
                guild = self.config.guild_from_id(guild_id)
                if name in data.get("mcp_enabled_servers", []):
                    async with guild.mcp_enabled_servers() as enabled:
                        if name in enabled:
                            enabled.remove(name)
                if name in data.get("mcp_tool_access", {}):
                    async with guild.mcp_tool_access() as access:
                        access.pop(name, None)
            servers.pop(name)
        await self.invalidate_server(name)

    async def set_enabled(self, guild_id: int, name: str, enabled: bool):
        async with self.config.mcp_servers.get_lock():
            if name not in await self.config.mcp_servers():
                raise MCPError(f"Unknown MCP server `{name}`.")
            guild = self.config.guild_from_id(guild_id)
            async with guild.mcp_enabled_servers() as servers:
                if enabled and name not in servers:
                    servers.append(name)
                elif not enabled and name in servers:
                    servers.remove(name)
            if enabled:
                await guild.function_calling.set(True)
        if not enabled:
            await self.invalidate(guild_id, name)

    async def tools_for_guild(
        self, guild: discord.Guild, member: discord.Member | None = None
    ) -> list[MCPToolCall]:
        configured = await self.config.mcp_servers()
        guild_config = self.config.guild(guild)
        enabled = set(await guild_config.mcp_enabled_servers())
        access = await guild_config.mcp_tool_access()
        active = [
            (server_alias, server)
            for server_alias, server in configured.items()
            if server_alias in enabled and isinstance(server, dict)
        ]
        results = await asyncio.gather(
            *(self.tools_for_mcp_server(guild.id, *item) for item in active),
            return_exceptions=True,
        )
        tools: list[MCPToolCall] = []
        for (server_alias, _), result in zip(active, results):
            if isinstance(result, BaseException):
                logger.warning(
                    "Could not load tools from MCP server %s (%s)",
                    server_alias,
                    type(result).__name__,
                )
            else:
                tools.extend(
                    tool
                    for tool in result
                    if allows_tool(
                        access.get(server_alias, {}), tool.native_name, member
                    )
                )
        return tools

    async def can_call(
        self,
        guild: discord.Guild,
        member: discord.Member | None,
        server_alias: str,
        tool: str,
    ) -> bool:
        config = self.config.guild(guild)
        return (
            await config.function_calling()
            and server_alias in await config.mcp_enabled_servers()
            and allows_tool(
                (await config.mcp_tool_access()).get(server_alias, {}), tool, member
            )
        )

    async def tools_for_mcp_server(
        self,
        guild_id: int,
        server_alias: str,
        server: dict[str, Any],
        refresh: bool = False,
    ) -> list[MCPToolCall]:
        client = await self._get_client(guild_id, server_alias, server)
        catalog = await client.list_tools(refresh=refresh)
        return [MCPToolCall(client, server_alias, tool) for tool in catalog]

    async def _get_client(
        self, guild_id: int, server_alias: str, server: dict[str, Any]
    ) -> MCPClient:
        cache_key = (guild_id, server_alias)
        fingerprint = json.dumps(server, sort_keys=True, separators=(",", ":"))
        async with self._lock:
            if self.phase is not ManagerPhase.OPEN:
                raise MCPError("The MCP manager is closed.")
            cached = self._clients.get(cache_key)
            if cached and cached[0] == fingerprint:
                return cached[1]
            headers = await self._resolve_headers(server_alias)
            client = MCPClient(server_alias, server["url"], headers, self.version)
            client.oauth = self.oauth
            old = self._clients.pop(cache_key, None)
            self._clients[cache_key] = (fingerprint, client)
            if old is None:
                return client
        await old[1].close()
        async with self._lock:
            if self.phase is not ManagerPhase.OPEN:
                raise MCPError("The MCP manager is closed.")
            if self._clients.get(cache_key) != (fingerprint, client):
                raise MCPError("The MCP server changed while connecting. Try again.")
            return client

    async def _resolve_headers(self, server_alias: str) -> dict[str, str]:
        secret = (await self.bot.get_shared_api_tokens(f"mcp_{server_alias}")).get(
            "token"
        )
        if not secret:
            return {}
        return {"Authorization": f"Bearer {secret}"}

    async def invalidate(self, guild_id: int, server_alias: str) -> None:
        async with self._lock:
            cached = self._clients.pop((guild_id, server_alias), None)
        if cached:
            await cached[1].close()

    async def invalidate_server(self, server_alias: str) -> None:
        async with self._lock:
            clients = [
                self._clients.pop(cache_key)[1]
                for cache_key in list(self._clients)
                if cache_key[1] == server_alias
            ]
        await asyncio.gather(*(client.close() for client in clients))

    async def tokens_updated(self, service: str) -> None:
        if service.startswith("mcp_"):
            await self.invalidate_server(service[4:])

    async def close(self) -> None:
        async with self._close_lock:
            async with self._lock:
                if self.phase is ManagerPhase.CLOSED:
                    return
                self.phase = ManagerPhase.CLOSING
                self._closing_clients.extend(
                    client for _, client in self._clients.values()
                )
                self._clients.clear()
            await asyncio.gather(
                *(client.close() for client in self._closing_clients),
                return_exceptions=True,
            )
            self._closing_clients.clear()
            await self.oauth.close()
            async with self._lock:
                self.phase = ManagerPhase.CLOSED
