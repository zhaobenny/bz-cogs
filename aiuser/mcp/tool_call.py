from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from aiuser.functions.context import ToolContext
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, ToolCallSchema
from aiuser.mcp.client import (
    MCPAuthError,
    MCPClient,
    MCPError,
    MCPOAuthRequired,
    MCPTimeoutError,
    MCPUnavailableError,
)

logger = logging.getLogger("red.bz_cogs.aiuser.mcp")
MAX_RESULT_CHARS = 64 * 1024


def model_tool_name(server_alias: str, native_name: str) -> str:
    raw = f"mcp__{server_alias}__{native_name}"
    normalized = re.sub(r"[^A-Za-z0-9_-]", "_", raw)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"{normalized[:55]}_{digest}"


class MCPToolCall(ToolCall):
    def __init__(self, client: MCPClient, server_alias: str, tool: dict[str, Any]):
        self.client = client
        self.server_alias = server_alias
        self.native_name = tool["name"]
        self.function_name = model_tool_name(server_alias, self.native_name)
        description = tool.get("description") or tool.get("title") or self.native_name
        self.schema = ToolCallSchema(
            Function(
                name=self.function_name,
                description=description,
                parameters=tool["inputSchema"],
            )
        )

    async def _handle(
        self, tool_context: ToolContext, arguments: dict[str, Any]
    ) -> str:
        label = f"{self.server_alias}.{self.native_name}"
        try:
            result = await self.client.call_tool(self.native_name, arguments)
            if result.get("resultType", "complete") != "complete":
                return "This MCP tool requires an interaction aiuser does not support."
            rendered = self._render_result(result)
            if result.get("isError"):
                rendered = f"MCP tool reported an error:\n{rendered}"
            if len(rendered) > MAX_RESULT_CHARS:
                return rendered[: MAX_RESULT_CHARS - 18] + "...\n[MCP result cut]"
            return rendered
        except MCPTimeoutError:
            return f'MCP tool "{label}" timed out; it may or may not have completed.'
        except MCPOAuthRequired:
            logger.warning(
                "MCP server %s requires OAuth sign-in",
                self.server_alias,
            )
            return (
                f'MCP server "{self.server_alias}" needs sign-in. '
                "An owner must remove and add the server again to authenticate."
            )
        except MCPAuthError:
            return (
                f'MCP server "{self.server_alias}" rejected its configured credentials.'
            )
        except MCPUnavailableError:
            return f'MCP server "{self.server_alias}" is unavailable.'
        except MCPError:
            return (
                f'MCP tool "{label}" failed because the server returned an invalid '
                "response."
            )

    @staticmethod
    def _render_result(result: dict[str, Any]) -> str:
        chunks: list[str] = []
        for item in result.get("content") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                chunks.append(item["text"])
            elif item.get("type"):
                chunks.append(f"[MCP {item['type']} content omitted]")
        structured = result.get("structuredContent")
        if structured is not None:
            chunks.append(
                json.dumps(structured, ensure_ascii=False, separators=(",", ":"))
            )
        return "\n".join(chunks) or "MCP tool completed without textual output."
