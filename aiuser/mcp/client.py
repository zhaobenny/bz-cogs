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
CATALOG_TTL = 3600
HEADER_TOKEN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


class MCPError(Exception):
    pass


class MCPAuthError(MCPError):
    pass


class MCPOAuthRequired(MCPAuthError):
    # Preserve the server challenge needed to begin OAuth authorization.
    def __init__(self, message="MCP authorization is required.", challenge=""):
        super().__init__(message)
        self.challenge = challenge


class MCPTimeoutError(MCPError):
    pass


class MCPUnavailableError(MCPError):
    pass


class MCPSessionExpired(MCPError):
    pass


class MCPFallback(MCPError):
    pass


class MCPClient:
    # Initialize connection, concurrency, catalog, and HTTP client state.
    def __init__(
        self, server_alias: str, url: str, headers: dict[str, str], version: str
    ):
        self.server_alias = server_alias
        self.url = url
        self.headers = headers
        self.oauth = None
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
        self._tool_headers: dict[str, list[tuple[tuple[str, ...], str]]] = {}
        self._catalog_time = 0.0
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(60, connect=10, write=10, pool=10),
            follow_redirects=False,
        )

    # Negotiate the modern protocol or fall back to legacy initialization.
    async def connect(self) -> None:
        async with self._connect_lock:
            if self.protocol_version:
                return

            try:
                result = await self._rpc("server/discover", {}, version=MODERN_VERSION)
                if MODERN_VERSION in result.get("supportedVersions", []):
                    self._set_server(result, MODERN_VERSION)
                    return
            except MCPFallback:
                pass

            result = await self._rpc(
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
            self._set_server(result, protocol_version)
            await self._notify("notifications/initialized")

    # Store the negotiated protocol, capabilities, and server identity.
    def _set_server(self, result: dict[str, Any], version: str) -> None:
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

    # Return the cached tool catalog or fetch a fresh copy.
    async def list_tools(self, refresh: bool = False) -> list[dict[str, Any]]:
        await self.connect()
        async with self._catalog_lock:
            if (
                not refresh
                and self._catalog is not None
                and time.monotonic() - self._catalog_time < CATALOG_TTL
            ):
                return self._catalog
            try:
                tools = await self._fetch_tools()
            except MCPSessionExpired:
                self._reset()
                await self.connect()
                tools = await self._fetch_tools()
            self._catalog = tools
            self._catalog_time = time.monotonic()
            return tools

    # Fetch and validate every page of the server's tool catalog.
    async def _fetch_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        cursor: str | None = None
        cursors = set()
        while True:
            params = {"cursor": cursor} if cursor else {}
            result = await self._rpc("tools/list", params)
            page = result.get("tools")
            if not isinstance(page, list):
                raise MCPError("The MCP server returned an invalid tool catalog.")
            for tool in page:
                if (
                    not isinstance(tool, dict)
                    or not isinstance(tool.get("name"), str)
                    or not tool["name"]
                    or not isinstance(tool.get("inputSchema"), dict)
                ):
                    logger.warning(
                        "Skipping malformed tool from MCP server %s", self.server_alias
                    )
                    continue
                name = tool["name"]
                tools.append(tool)
                self._tool_headers[name] = self._find_headers(tool)
            cursor = result.get("nextCursor")
            if not cursor:
                return tools
            if not isinstance(cursor, str) or cursor in cursors:
                raise MCPError("The MCP server returned invalid tool pagination.")
            cursors.add(cursor)

    # Find tool arguments that must also be sent as HTTP headers.
    @staticmethod
    def _find_headers(tool: dict[str, Any]) -> list[tuple[tuple[str, ...], str]]:
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict):
            return []

        found: list[tuple[tuple[str, ...], str]] = []

        # Recursively inspect nested object properties for header annotations.
        def walk_properties(schema: dict[str, Any], path: tuple[str, ...]) -> None:
            properties = schema.get("properties") or {}
            if not isinstance(properties, dict):
                return
            for key, value in properties.items():
                if not isinstance(value, dict):
                    continue
                header = value.get("x-mcp-header")
                if header is not None:
                    found.append((path + (key,), header))
                walk_properties(value, path + (key,))

        walk_properties(schema, ())

        return [
            (path, header)
            for path, header in found
            if isinstance(header, str) and HEADER_TOKEN.fullmatch(header)
        ]

    # Call one server tool while enforcing the concurrency limit.
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self.connect()
        if self._catalog is None:
            await self.list_tools()
        request_headers = self._call_headers(name, arguments)
        async with self._call_limit:
            try:
                return await self._rpc(
                    "tools/call",
                    {"name": name, "arguments": arguments},
                    headers=request_headers,
                )
            except MCPSessionExpired:
                self._reset()
                raise

    # Build HTTP headers from annotated tool argument values.
    def _call_headers(self, name: str, arguments: dict[str, Any]) -> dict[str, str]:
        headers = {}
        for path, header in self._tool_headers.get(name, []):
            value: Any = arguments
            for key in path:
                if not isinstance(value, dict) or key not in value:
                    value = None
                    break
                value = value[key]
            if value is None:
                continue
            text = str(value).lower() if isinstance(value, bool) else str(value)
            headers[f"Mcp-Param-{header}"] = self._encode_header(text)
        return headers

    # Encode values that cannot be placed directly in an HTTP header.
    @staticmethod
    def _encode_header(value: str) -> str:
        safe = (
            value == value.strip()
            and all(char == "\t" or 0x20 <= ord(char) <= 0x7E for char in value)
            and not (value.startswith("=?base64?") and value.endswith("?="))
        )
        if safe:
            return value
        encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
        return f"=?base64?{encoded}?="

    # Send a JSON-RPC request and validate its matching result.
    async def _rpc(
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
        response = await self._request(payload, request_id, protocol_version, headers)
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

    # Send a JSON-RPC notification that has no response.
    async def _notify(self, method: str) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        await self._request(payload, None, self.protocol_version)

    # Apply headers, authentication, retries, timeouts, and network errors.
    async def _request(
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
                headers["Mcp-Name"] = self._encode_header(name)
        elif self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        access = None
        if self.oauth:
            access = await self.oauth.access_token(self.server_alias, self.url)
            if access:
                headers["Authorization"] = f"Bearer {access}"
        try:
            try:
                return await asyncio.wait_for(
                    self._post(payload, headers, request_id), timeout=60
                )
            except MCPOAuthRequired:
                if not access:
                    raise
                access = await self.oauth.access_token(
                    self.server_alias, self.url, rejected=access
                )
                if not access:
                    raise
                headers["Authorization"] = f"Bearer {access}"
                return await asyncio.wait_for(
                    self._post(payload, headers, request_id), timeout=60
                )
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise MCPTimeoutError("The MCP request timed out.") from exc
        except httpx.RequestError as exc:
            raise MCPUnavailableError("The MCP server is unavailable.") from exc

    # Perform one HTTP POST and parse its JSON or SSE response.
    async def _post(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        request_id: int | None,
    ) -> dict[str, Any] | None:
        async with self._http.stream(
            "POST", self.url, headers=headers, json=payload
        ) as response:
            self._check_status(response, payload)
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

    # Convert HTTP failures into specific MCP exceptions.
    def _check_status(self, response: httpx.Response, payload: dict[str, Any]) -> None:
        if response.status_code in (401, 403):
            challenge = response.headers.get("WWW-Authenticate", "")
            if response.status_code == 401 or "resource_metadata" in challenge:
                raise MCPOAuthRequired(challenge=challenge)
            raise MCPAuthError("The MCP server rejected its configured credentials.")
        if response.status_code == 404 and self.session_id:
            raise MCPSessionExpired("The MCP session expired.")
        if response.status_code < 400:
            return
        legacy_response = payload.get(
            "method"
        ) == "server/discover" and response.status_code in (
            400,
            404,
            405,
        )
        if legacy_response:
            raise MCPFallback("The server uses legacy MCP.")
        if response.status_code >= 500:
            raise MCPUnavailableError("The MCP server is unavailable.")
        raise MCPError(f"The MCP server returned HTTP {response.status_code}.")

    # Read a response body while enforcing the size limit.
    @staticmethod
    async def _read_bytes(response: httpx.Response) -> bytes:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise MCPError("The MCP response exceeded the size limit.")
        return bytes(body)

    # Read SSE events until the matching JSON-RPC response arrives.
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
                    message = MCPClient._parse_sse(raw, request_id)
                    if message is not None:
                        return message
                continue
            if line.startswith("data:"):
                data.append(line[6:] if line.startswith("data: ") else line[5:])
        # An incomplete event at EOF is discarded by the SSE stream format.
        raise MCPError("The MCP stream ended before returning a response.")

    # Parse one SSE event and return it only when its request ID matches.
    @staticmethod
    def _parse_sse(raw: str, request_id: int) -> dict[str, Any] | None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MCPError("The MCP server returned invalid SSE data.") from exc
        if isinstance(message, dict) and message.get("id") == request_id:
            return message
        return None

    # Clear negotiated state so the next operation reconnects.
    def _reset(self) -> None:
        self.protocol_version = None
        self.session_id = None
        self.server_info = {}
        self.capabilities = {}
        self._catalog = None
        self._tool_headers.clear()

    # Close any legacy session and release the HTTP client.
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
