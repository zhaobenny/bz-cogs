from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import discord
from redbot.core import Config
from redbot.core.bot import Red

from aiuser.mcp.client import MCPClient
from aiuser.mcp.oauth import MCPOAuth
from aiuser.mcp.tool_call import MCPToolCall

logger = logging.getLogger("red.bz_cogs.aiuser.mcp")


class MCPManager:
    def __init__(self, bot: Red, config: Config, version: str):
        self.bot = bot
        self.config = config
        self.version = version
        self.oauth = MCPOAuth(bot)
        self._clients: dict[tuple[int, str], tuple[str, MCPClient]] = {}
        self._lock = asyncio.Lock()

    async def tools_for_guild(self, guild: discord.Guild) -> list[MCPToolCall]:
        configured = await self.config.mcp_servers()
        enabled = set(await self.config.guild(guild).mcp_enabled_servers())
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
                tools.extend(result)
        return tools

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
            cached = self._clients.get(cache_key)
            if cached and cached[0] == fingerprint:
                return cached[1]
            headers = await self._resolve_headers(server_alias)
            client = MCPClient(server_alias, server["url"], headers, self.version)
            client.oauth = self.oauth
            old = self._clients.pop(cache_key, None)
            self._clients[cache_key] = (fingerprint, client)
            if old:
                await old[1].close()
            return client

    async def _resolve_headers(self, server_alias: str) -> dict[str, str]:
        secret = (await self.bot.get_shared_api_tokens(f"mcp_{server_alias}")).get(
            "token"
        )
        if not secret:
            return {}
        return {"Authorization": f"Bearer {secret}"}

    async def invalidate(self, guild_id: int, server_alias: str) -> None:
        cached = self._clients.pop((guild_id, server_alias), None)
        if cached:
            await cached[1].close()

    async def invalidate_server(self, server_alias: str) -> None:
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
        self.oauth.pending.clear()
        clients = [client for _, client in self._clients.values()]
        self._clients.clear()
        await asyncio.gather(
            *(client.close() for client in clients), return_exceptions=True
        )
