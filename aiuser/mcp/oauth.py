from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
from urllib.parse import parse_qs, urlsplit

import httpx
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.httpx_client import AsyncOAuth2Client

from .client import MCPError, MCPOAuthRequired

REDIRECT_URI = "http://localhost:8765/callback"
LOGIN_SECONDS = 600


class MCPOAuth:
    def __init__(self, bot):
        self.bot = bot
        self.pending = {}
        self.locks = {}

    def lock(self, alias):
        return self.locks.setdefault(alias, asyncio.Lock())

    async def load(self, alias):
        secret = await self.bot.get_shared_api_tokens(f"aiuser_mcp_oauth_{alias}")
        if not secret.get("oauth"):
            return {}
        try:
            return json.loads(secret["oauth"])
        except (TypeError, ValueError):
            raise MCPError(
                "MCP credentials could not be read. Remove and add this server again."
            ) from None

    async def save(self, alias, data):
        await self.bot.set_shared_api_tokens(
            f"aiuser_mcp_oauth_{alias}",
            oauth=json.dumps(data),
        )

    async def forget(self, alias):
        async with self.lock(alias):
            self.pending.pop(alias, None)
            await self.bot.remove_shared_api_tokens(
                f"aiuser_mcp_oauth_{alias}", "oauth"
            )

    async def metadata(self, client, urls):
        for url in dict.fromkeys(urls):
            async with client.stream("GET", url) as response:
                if response.status_code in (404, 405):
                    continue
                if not response.is_success:
                    raise MCPError("OAuth discovery failed. Retry enabling the server.")
                from .client import MCPClient

                data = json.loads(await MCPClient._read_bytes(response))
                if not isinstance(data, dict):
                    raise MCPError("The server returned invalid OAuth metadata.")
                return data
        raise MCPError("The server does not publish OAuth discovery metadata.")

    async def begin(self, alias, url, challenge, owner_id, guild_id):
        async with self.lock(alias):
            self.pending.pop(alias, None)
            try:
                return await self._begin(alias, url, challenge, owner_id, guild_id)
            except MCPError:
                raise
            except (
                AuthlibBaseError,
                httpx.HTTPError,
                KeyError,
                OSError,
                TypeError,
                ValueError,
            ):
                raise MCPError(
                    "OAuth setup failed. Retry enabling the server."
                ) from None

    async def _begin(
        self, alias, url: str, challenge, owner_id, guild_id
    ) -> tuple[str, str]:
        # Find the protected resource metadata before the authorization server.
        resource_url = urlsplit(url)
        resource_origin = f"{resource_url.scheme}://{resource_url.netloc}"
        resource_match = re.search(
            r'\bresource_metadata\s*=\s*"([^"\r\n]+)"', challenge, re.IGNORECASE
        )
        resource_metadata_urls = (
            [resource_match[1]]
            if resource_match
            else [
                resource_origin
                + "/.well-known/oauth-protected-resource"
                + resource_url.path,
                resource_origin + "/.well-known/oauth-protected-resource",
            ]
        )
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as http:
            legacy = False
            try:
                resource_metadata = await self.metadata(http, resource_metadata_urls)
            except MCPError as exc:
                if (
                    resource_match is not None
                    or str(exc)
                    != "The server does not publish OAuth discovery metadata."
                ):
                    raise
                legacy = True
                resource_metadata = {}
            if legacy:
                issuer = resource_origin
            else:
                if resource_metadata.get("resource") != url:
                    raise MCPError(
                        "OAuth resource metadata does not match the configured MCP URL."
                    )
                authorization_servers = resource_metadata.get("authorization_servers")
                if (
                    not isinstance(authorization_servers, list)
                    or not authorization_servers
                ):
                    raise MCPError("The MCP server does not advertise an OAuth issuer.")
                issuer = authorization_servers[0]
            issuer_url = urlsplit(issuer)
            issuer_origin = f"{issuer_url.scheme}://{issuer_url.netloc}"
            issuer_path = issuer_url.path.rstrip("/")
            issuer_metadata_urls = (
                [issuer_origin + "/.well-known/oauth-authorization-server"]
                if legacy
                else [
                    issuer_origin
                    + "/.well-known/oauth-authorization-server"
                    + issuer_path,
                    issuer_origin + "/.well-known/openid-configuration" + issuer_path,
                    issuer.rstrip("/") + "/.well-known/openid-configuration",
                ]
            )
            try:
                provider_metadata = await self.metadata(http, issuer_metadata_urls)
            except MCPError as exc:
                if (
                    not legacy
                    or str(exc)
                    != "The server does not publish OAuth discovery metadata."
                ):
                    raise
                provider_metadata = {}
            if provider_metadata:
                if provider_metadata.get("issuer") != issuer:
                    raise MCPError("OAuth discovery returned a different issuer.")
                if "S256" not in provider_metadata.get(
                    "code_challenge_methods_supported", []
                ):
                    raise MCPError(
                        "This OAuth provider does not advertise secure PKCE support."
                    )
            authorization_endpoint = provider_metadata.get(
                "authorization_endpoint", issuer_origin + "/authorize"
            )
            token_endpoint = provider_metadata.get(
                "token_endpoint", issuer_origin + "/token"
            )
            # Reuse a matching public client, or register one for this issuer.
            saved = await self.load(alias)
            registration = (
                saved.get("registration")
                if (saved.get("url") == url and saved.get("issuer") == issuer)
                else None
            )
            if not registration:
                registration_endpoint = provider_metadata.get("registration_endpoint")
                if legacy and not registration_endpoint:
                    registration_endpoint = issuer_origin + "/register"
                if not registration_endpoint:
                    raise MCPError(
                        "This provider requires a pre-registered OAuth client; automatic registration is unavailable."
                    )
                response = await http.post(
                    registration_endpoint,
                    json={
                        "client_name": "aiuser MCP",
                        "redirect_uris": [REDIRECT_URI],
                        "grant_types": ["authorization_code", "refresh_token"],
                        "response_types": ["code"],
                        "token_endpoint_auth_method": "none",
                    },
                )
                if not response.is_success:
                    raise MCPError(
                        "OAuth client registration failed. Retry enabling the server."
                    )
                registration = response.json()
                if not isinstance(registration.get("client_id"), str):
                    raise MCPError("OAuth registration did not return a client ID.")
                if registration.get("token_endpoint_auth_method", "none") != "none":
                    raise MCPError(
                        "This provider did not register a public OAuth client."
                    )
                registration = {"client_id": registration["client_id"]}
            scope_match = re.search(
                r'\bscope\s*=\s*"([^"\r\n]*)"', challenge, re.IGNORECASE
            )
            scopes = resource_metadata.get(
                "scopes_supported", provider_metadata.get("scopes_supported", [])
            )
            scope = scope_match[1] if scope_match else " ".join(scopes)
            data = {
                "url": url,
                "issuer": issuer,
                "endpoint": token_endpoint,
                "registration": registration,
            }
            # Preserve registration across retries without replacing an existing account.
            if not saved.get("token"):
                await self.save(alias, data)
            state = secrets.token_urlsafe(32)
            verifier = secrets.token_urlsafe(64)
            async with AsyncOAuth2Client(
                registration["client_id"],
                token_endpoint_auth_method="none",
                redirect_uri=REDIRECT_URI,
                scope=scope,
                code_challenge_method="S256",
            ) as oauth:
                link, _ = oauth.create_authorization_url(
                    authorization_endpoint,
                    state=state,
                    code_verifier=verifier,
                    resource=url,
                )
            self.pending[alias] = {
                "data": data,
                "state": state,
                "verifier": verifier,
                "owner_id": owner_id,
                "guild_id": guild_id,
                "deadline": time.monotonic() + LOGIN_SECONDS,
            }
            return link, state

    @staticmethod
    def _parse_callback(callback: str, state: str, issuer: str) -> dict[str, list[str]]:
        parsed = urlsplit(callback.strip())
        expected = urlsplit(REDIRECT_URI)
        if (parsed.scheme, parsed.netloc, parsed.path) != (
            expected.scheme,
            expected.netloc,
            expected.path,
        ) or parsed.fragment:
            raise ValueError()
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
        if any(len(values) != 1 for values in query.values()):
            raise ValueError()
        if not secrets.compare_digest(query.get("state", [""])[0], state):
            raise ValueError()
        if "iss" in query and query["iss"][0] != issuer:
            raise ValueError()
        return query

    async def finish(self, alias, state, owner_id, callback):
        async with self.lock(alias):
            pending = self.pending.get(alias)
            if (
                not pending
                or pending.get("consumed")
                or pending["state"] != state
                or time.monotonic() > pending["deadline"]
            ):
                raise MCPError(
                    "This login expired or was replaced. Remove and add this server again."
                )
            if pending["owner_id"] != owner_id:
                raise MCPError("Only the owner who started this login can finish it.")
            try:
                query = self._parse_callback(callback, state, pending["data"]["issuer"])
            except (ValueError, TypeError):
                raise MCPError(
                    "That callback URL is invalid. Copy the full final localhost URL and try again."
                ) from None
            if "error" in query:
                self.pending.pop(alias, None)
                raise MCPError(
                    "Sign-in was denied or cancelled. Remove and add this server again to retry."
                )
            code = query.get("code", [""])[0]
            if not code:
                raise MCPError(
                    "The callback has no authorization code. Copy the full final URL."
                )
            # Codes are single use, including ambiguous failures.
            pending["consumed"] = True
            data = pending["data"]
            try:
                async with AsyncOAuth2Client(
                    data["registration"]["client_id"],
                    token_endpoint_auth_method="none",
                    redirect_uri=REDIRECT_URI,
                    timeout=20,
                    follow_redirects=False,
                ) as oauth:
                    token = await oauth.fetch_token(
                        data["endpoint"],
                        grant_type="authorization_code",
                        code=code,
                        code_verifier=pending["verifier"],
                        resource=data["url"],
                    )
                if (
                    not token.get("access_token")
                    or token.get("token_type", "").lower() != "bearer"
                ):
                    raise ValueError()
                data["token"] = dict(token)
                await self.save(alias, data)
            except (
                AuthlibBaseError,
                httpx.HTTPError,
                KeyError,
                OSError,
                TypeError,
                ValueError,
            ):
                raise MCPError(
                    "The code could not be exchanged. Remove and add this server again to start over."
                ) from None
            return pending["guild_id"], data["url"]

    async def access_token(self, alias, url: str, rejected=None):
        async with self.lock(alias):
            data = await self.load(alias)
            token = data.get("token")
            if not token or data.get("url") != url:
                return None
            current_access_token = token.get("access_token")
            if rejected and rejected != current_access_token:
                # Another request already rotated this token.
                return current_access_token
            token_is_fresh = not rejected and (
                not token.get("expires_at") or token["expires_at"] > time.time() + 60
            )
            if token_is_fresh:
                return current_access_token
            if not token.get("refresh_token"):
                raise MCPOAuthRequired(
                    "MCP sign-in expired. Remove and add this server again."
                )
            try:
                refresh_token = token["refresh_token"]
                async with AsyncOAuth2Client(
                    data["registration"]["client_id"],
                    token_endpoint_auth_method="none",
                    token=token,
                    timeout=20,
                    follow_redirects=False,
                ) as oauth:
                    updated = dict(
                        await oauth.refresh_token(
                            data["endpoint"],
                            refresh_token=refresh_token,
                            resource=url,
                        )
                    )
                if (
                    not updated.get("access_token")
                    or updated.get("token_type", "").lower() != "bearer"
                ):
                    raise ValueError()
                updated.setdefault("refresh_token", refresh_token)
                data["token"] = updated
                await self.save(alias, data)
                return updated["access_token"]
            except asyncio.CancelledError:
                data.pop("token", None)
                await asyncio.shield(self.save(alias, data))
                raise
            except (
                AuthlibBaseError,
                httpx.HTTPError,
                KeyError,
                OSError,
                TypeError,
                ValueError,
            ):
                # Do not replay a refresh token after an ambiguous rotation failure.
                data.pop("token", None)
                await self.save(alias, data)
                raise MCPOAuthRequired(
                    "MCP sign-in expired. Remove and add this server again."
                ) from None
