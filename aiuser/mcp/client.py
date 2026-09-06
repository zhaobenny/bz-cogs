from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger("red.bz_cogs.aiuser.mcp")

MODERN_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-11-25"
LEGACY_VERSIONS = {LEGACY_VERSION, "2025-06-18", "2025-03-26"}
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_RESULT_CHARS = 64 * 1024
CATALOG_TTL = 300


class MCPError(Exception):
    pass


class MCPAuthError(MCPError):
    pass


class MCPOAuthRequired(MCPAuthError):
    pass


class MCPTimeoutError(MCPError):
    pass


class MCPUnavailableError(MCPError):
    pass


class MCPSessionExpired(MCPError):
    pass


class MCPFallback(MCPError):
    pass


class MCPClient:
    def __init__(
        self, server_alias: str, url: str, headers: dict[str, str], version: str
    ):
        self.server_alias = server_alias
        self.url = url
        self.headers = headers
        self.client_info = {"name": "aiuser", "version": version}
        self.protocol_version: str | None = None
        self.server_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        self.session_id: str | None = None
        self._request_id = 0
        self._connect_lock = asyncio.Lock()
        self._catalog_lock = asyncio.Lock()
        self._call_limit = asyncio.Semaphore(4)
        self._catalog: list[dict[str, Any]] | None = None
        self._tool_headers: dict[str, list[tuple[tuple[str, ...], str, str]]] = {}
        self._catalog_time = 0.0
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(60, connect=10, write=10, pool=10),
            follow_redirects=False,
        )

    async def connect(self) -> None:
        if self.protocol_version:
            return
        async with self._connect_lock:
            if self.protocol_version:
                return
            try:
                result = await self._request(
                    "server/discover", {}, version=MODERN_VERSION
                )
                if MODERN_VERSION in result.get("supportedVersions", []):
                    self._set_server_details(result, MODERN_VERSION)
                    return
            except MCPFallback:
                pass

            result = await self._request(
                "initialize",
                {
                    "protocolVersion": LEGACY_VERSION,
                    "capabilities": {},
                    "clientInfo": self.client_info,
                },
            )
            protocol_version = result.get("protocolVersion")
            if protocol_version not in LEGACY_VERSIONS:
                raise MCPError("The server negotiated an unsupported MCP version.")
            self._set_server_details(result, protocol_version)
            await self._notify("notifications/initialized")

    def _set_server_details(self, result: dict[str, Any], version: str) -> None:
        capabilities = result.get("capabilities")
        if not isinstance(capabilities, dict) or "tools" not in capabilities:
            raise MCPError("The MCP server does not advertise tool support.")
        self.protocol_version = version
        self.capabilities = capabilities
        server_info = result.get("serverInfo")
        if version == MODERN_VERSION:
            server_info = (result.get("_meta") or {}).get(
                "io.modelcontextprotocol/serverInfo"
            )
        if isinstance(server_info, dict):
            self.server_info = server_info

    async def list_tools(self, refresh: bool = False) -> list[dict[str, Any]]:
        await self.connect()
        if (
            not refresh
            and self._catalog is not None
            and time.monotonic() - self._catalog_time < CATALOG_TTL
        ):
            return self._catalog

        async with self._catalog_lock:
            if (
                not refresh
                and self._catalog is not None
                and time.monotonic() - self._catalog_time < CATALOG_TTL
            ):
                return self._catalog
            try:
                tools = await self._list_all_tools()
            except MCPSessionExpired:
                self._reset_session()
                await self.connect()
                tools = await self._list_all_tools()
            self._catalog = tools
            self._catalog_time = time.monotonic()
            return tools

    async def _list_all_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        cursor: str | None = None
        cursors = set()
        names = set()
        while True:
            params = {"cursor": cursor} if cursor else {}
            result = await self._request("tools/list", params)
            page = result.get("tools")
            if not isinstance(page, list):
                raise MCPError("The MCP server returned an invalid tool catalog.")
            for tool in page:
                header_fields = self._header_fields(tool)
                if header_fields is None:
                    logger.warning(
                        "Skipping malformed tool from MCP server %s", self.server_alias
                    )
                    continue
                if tool["name"] in names:
                    logger.warning(
                        "Skipping duplicate tool %s from MCP server %s",
                        tool["name"],
                        self.server_alias,
                    )
                    continue
                tools.append(tool)
                names.add(tool["name"])
                self._tool_headers[tool["name"]] = header_fields
            cursor = result.get("nextCursor")
            if not cursor:
                return tools
            if not isinstance(cursor, str) or cursor in cursors:
                raise MCPError("The MCP server returned invalid tool pagination.")
            cursors.add(cursor)

    @staticmethod
    def _header_fields(tool: Any) -> list[tuple[tuple[str, ...], str, str]] | None:
        if not (
            isinstance(tool, dict)
            and isinstance(tool.get("name"), str)
            and tool["name"]
            and isinstance(tool.get("inputSchema"), dict)
            and tool["inputSchema"].get("type") == "object"
        ):
            return None
        found: list[tuple[tuple[str, ...], str, str]] = []

        def walk_properties(schema: dict[str, Any], path: tuple[str, ...]) -> None:
            properties = schema.get("properties") or {}
            if not isinstance(properties, dict):
                return
            for key, value in properties.items():
                if not isinstance(value, dict):
                    continue
                header = value.get("x-mcp-header")
                if header is not None:
                    found.append((path + (key,), header, value.get("type")))
                walk_properties(value, path + (key,))

        walk_properties(tool["inputSchema"], ())

        def annotation_count(value: Any) -> int:
            if isinstance(value, dict):
                return ("x-mcp-header" in value) + sum(
                    annotation_count(item) for item in value.values()
                )
            if isinstance(value, list):
                return sum(annotation_count(item) for item in value)
            return 0

        token = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
        headers = [field[1] for field in found]
        if (
            annotation_count(tool["inputSchema"]) != len(found)
            or any(
                not isinstance(header, str)
                or not token.fullmatch(header)
                or field_type not in ("string", "integer", "boolean")
                for _, header, field_type in found
            )
            or len({header.lower() for header in headers}) != len(headers)
        ):
            return None
        return found

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        await self.connect()
        request_headers = self._tool_call_headers(name, arguments)
        async with self._call_limit:
            result = await self._request(
                "tools/call",
                {"name": name, "arguments": arguments},
                headers=request_headers,
            )
        if result.get("resultType", "complete") != "complete":
            return "This MCP tool requires an interaction aiuser does not support."
        rendered = self._render_result(result)
        if result.get("isError"):
            rendered = f"MCP tool reported an error:\n{rendered}"
        if len(rendered) > MAX_RESULT_CHARS:
            return rendered[: MAX_RESULT_CHARS - 18] + "\n[MCP result cut]"
        return rendered

    def _tool_call_headers(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, str]:
        headers = {}
        for path, header, field_type in self._tool_headers.get(name, []):
            value: Any = arguments
            for key in path:
                if not isinstance(value, dict) or key not in value:
                    value = None
                    break
                value = value[key]
            if value is None:
                continue
            valid = (
                (field_type == "string" and isinstance(value, str))
                or (
                    field_type == "integer"
                    and isinstance(value, int)
                    and not isinstance(value, bool)
                    and -(2**53) < value < 2**53
                )
                or (field_type == "boolean" and isinstance(value, bool))
            )
            if not valid:
                raise MCPError("MCP tool arguments do not match its header schema.")
            text = str(value).lower() if isinstance(value, bool) else str(value)
            headers[f"Mcp-Param-{header}"] = self._header_value(text)
        return headers

    @staticmethod
    def _header_value(value: str) -> str:
        safe = (
            value == value.strip()
            and all(char == "\t" or 0x20 <= ord(char) <= 0x7E for char in value)
            and not (value.startswith("=?base64?") and value.endswith("?="))
        )
        if safe:
            return value
        encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
        return f"=?base64?{encoded}?="

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

    async def _request(
        self,
        method: str,
        params: dict[str, Any],
        version: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        protocol_version = version or self.protocol_version
        if protocol_version == MODERN_VERSION:
            params = dict(params)
            params["_meta"] = {
                "io.modelcontextprotocol/protocolVersion": MODERN_VERSION,
                "io.modelcontextprotocol/clientInfo": self.client_info,
                "io.modelcontextprotocol/clientCapabilities": {},
            }
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        response = await self._post(payload, request_id, protocol_version, headers)
        if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
            raise MCPError("The MCP server returned an invalid JSON-RPC response.")
        if response.get("id") != request_id:
            raise MCPError("The MCP server returned a mismatched response.")
        if "error" in response:
            error = response.get("error") or {}
            logger.warning(
                "MCP server %s returned JSON-RPC error code %s for %s",
                self.server_alias,
                error.get("code"),
                method,
            )
            if method == "server/discover" and error.get("code") in (
                -32601,
                -32022,
            ):
                raise MCPFallback("The server uses legacy MCP.")
            raise MCPError("The MCP server rejected the request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPError("The MCP server returned an invalid result.")
        return result

    async def _notify(self, method: str) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        await self._post(payload, None, self.protocol_version)

    async def _post(
        self,
        payload: dict[str, Any],
        request_id: int | None,
        protocol_version: str | None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        headers = {
            **self.headers,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }
        method = payload.get("method")
        if protocol_version and protocol_version != "2025-03-26":
            headers["MCP-Protocol-Version"] = protocol_version
        if protocol_version == MODERN_VERSION:
            headers["Mcp-Method"] = method
            name = (payload.get("params") or {}).get("name")
            if name:
                headers["Mcp-Name"] = self._header_value(name)
        elif self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        try:
            return await asyncio.wait_for(
                self._read_post(payload, headers, request_id), timeout=60
            )
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise MCPTimeoutError("The MCP request timed out.") from exc
        except httpx.RequestError as exc:
            raise MCPUnavailableError("The MCP server is unavailable.") from exc

    async def _read_post(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        request_id: int | None,
    ) -> dict[str, Any] | None:
        async with self._http.stream(
            "POST", self.url, headers=headers, json=payload
        ) as response:
            if response.status_code in (401, 403):
                challenge = response.headers.get("WWW-Authenticate", "")
                if re.search(
                    r'\bbearer\b[^\r\n]*\bresource_metadata\s*=',
                    challenge,
                    re.IGNORECASE,
                ):
                    raise MCPOAuthRequired(
                        "This server requires OAuth authorization, which aiuser "
                        "does not support yet."
                    )
                raise MCPAuthError(
                    "The MCP server rejected its configured credentials."
                )
            if response.status_code == 404 and self.session_id:
                raise MCPSessionExpired("The MCP session expired.")
            if response.status_code >= 400:
                legacy_response = payload.get(
                    "method"
                ) == "server/discover" and response.status_code in (400, 404, 405)
                if legacy_response:
                    raise MCPFallback("The server uses legacy MCP.")
                if response.status_code >= 500:
                    raise MCPUnavailableError("The MCP server is unavailable.")
                raise MCPError(f"The MCP server returned HTTP {response.status_code}.")
            if payload.get("method") == "initialize":
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id and all(0x21 <= ord(char) <= 0x7E for char in session_id):
                    self.session_id = session_id
            if request_id is None:
                return None

            content_type = response.headers.get("content-type", "").lower()
            if "application/json" in content_type:
                body = await self._read_bytes(response)
                try:
                    return json.loads(body)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise MCPError("The MCP server returned invalid JSON.") from exc
            if "text/event-stream" in content_type:
                return await self._read_sse(response, request_id)
            raise MCPError("The MCP server returned an unsupported content type.")

    @staticmethod
    async def _read_bytes(response: httpx.Response) -> bytes:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise MCPError("The MCP response exceeded the size limit.")
        return bytes(body)

    @staticmethod
    async def _read_sse(response: httpx.Response, request_id: int) -> dict[str, Any]:
        data: list[str] = []
        size = 0
        async for line in response.aiter_lines():
            size += len(line.encode("utf-8")) + 1
            if size > MAX_RESPONSE_BYTES:
                raise MCPError("The MCP response exceeded the size limit.")
            if not line:
                if data:
                    raw = "\n".join(data)
                    data = []
                    if not raw:
                        continue
                    try:
                        message = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise MCPError(
                            "The MCP server returned invalid SSE data."
                        ) from exc
                    if isinstance(message, dict) and message.get("id") == request_id:
                        return message
                continue
            if line.startswith("data:"):
                data.append(line[6:] if line.startswith("data: ") else line[5:])
        if data:
            try:
                message = json.loads("\n".join(data))
            except json.JSONDecodeError as exc:
                raise MCPError("The MCP server returned invalid SSE data.") from exc
            if isinstance(message, dict) and message.get("id") == request_id:
                return message
        raise MCPError("The MCP stream ended before returning a response.")

    def _reset_session(self) -> None:
        self.protocol_version = None
        self.session_id = None
        self.server_info = {}
        self.capabilities = {}
        self._catalog = None
        self._tool_headers.clear()

    async def close(self) -> None:
        if self.session_id:
            headers = {**self.headers, "Mcp-Session-Id": self.session_id}
            if self.protocol_version:
                headers["MCP-Protocol-Version"] = self.protocol_version
            try:
                await self._http.delete(self.url, headers=headers)
            except httpx.HTTPError:
                logger.debug("Failed to close MCP session %s", self.server_alias)
        await self._http.aclose()
