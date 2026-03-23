import asyncio
import base64
import json
import logging
import time
from typing import Any, Dict, Optional

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from redbot.core import Config

logger = logging.getLogger("red.bz_cogs.aiuser.llm")

CODEX_ENDPOINT_MODE = "codex"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_ISSUER = "https://auth.openai.com"
CODEX_DEVICE_CODE_URL = f"{CODEX_ISSUER}/api/accounts/deviceauth/usercode"
CODEX_DEVICE_TOKEN_URL = f"{CODEX_ISSUER}/api/accounts/deviceauth/token"
CODEX_OAUTH_TOKEN_URL = f"{CODEX_ISSUER}/oauth/token"
CODEX_DEVICE_VERIFICATION_URL = f"{CODEX_ISSUER}/codex/device"
CODEX_REDIRECT_URI = f"{CODEX_ISSUER}/deviceauth/callback"
CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
CODEX_ALLOWED_MODELS = [
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex-mini",
    "gpt-5.2",
    "gpt-5.2-codex",
    "gpt-5.3-codex",
    "gpt-5.4",
]
CODEX_DEFAULT_MODEL = "gpt-5.4"
CODEX_POLLING_SAFETY_MARGIN_SECONDS = 3
CODEX_DEVICE_TIMEOUT_SECONDS = 300


def utc_now_ms() -> int:
    return int(time.time() * 1000)


def parse_jwt_claims(token: str) -> Optional[Dict[str, Any]]:
    parts = token.split(".")
    if len(parts) != 3:
        return None

    try:
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding)
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return None


def extract_account_id_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    openai_claims = claims.get("https://api.openai.com/auth", {})
    organizations = claims.get("organizations", [])
    return (
        claims.get("chatgpt_account_id")
        or openai_claims.get("chatgpt_account_id")
        or ((organizations[0] or {}).get("id") if organizations else None)
    )


def extract_account_id(tokens: Dict[str, Any]) -> Optional[str]:
    id_token = tokens.get("id_token")
    if id_token:
        claims = parse_jwt_claims(id_token)
        if claims:
            account_id = extract_account_id_from_claims(claims)
            if account_id:
                return account_id

    access_token = tokens.get("access_token")
    if access_token:
        claims = parse_jwt_claims(access_token)
        if claims:
            return extract_account_id_from_claims(claims)
    return None


def normalize_codex_tokens(
    tokens: Dict[str, Any],
    previous_account_id: Optional[str] = None,
    previous_refresh_token: Optional[str] = None,
) -> Dict[str, Any]:
    expires_in = int(tokens.get("expires_in") or 3600)
    return {
        "access": tokens.get("access_token"),
        "refresh": tokens.get("refresh_token") or previous_refresh_token,
        "expires": utc_now_ms() + (expires_in * 1000),
        "account_id": extract_account_id(tokens) or previous_account_id,
    }


async def is_codex_endpoint_mode(config: Config) -> bool:
    return await config.custom_openai_endpoint() == CODEX_ENDPOINT_MODE


async def get_codex_oauth(config: Config) -> Dict[str, Any]:
    return await config.get_raw("codex_oauth", default={})


async def set_codex_oauth(config: Config, oauth: Dict[str, Any]):
    await config.set_raw("codex_oauth", value=oauth)


async def start_device_authorization(
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    owns_client = client is None
    client = client or httpx.AsyncClient()
    try:
        response = await client.post(
            CODEX_DEVICE_CODE_URL,
            json={"client_id": CODEX_CLIENT_ID},
            headers={"User-Agent": "aiuser/1.5.0"},
        )
        response.raise_for_status()
        data = response.json()
        return {
            "device_auth_id": data["device_auth_id"],
            "user_code": data["user_code"],
            "interval": max(int(data.get("interval") or 5), 1),
            "verification_url": CODEX_DEVICE_VERIFICATION_URL,
        }
    finally:
        if owns_client:
            await client.aclose()


async def exchange_device_authorization(
    device_auth_id: str,
    user_code: str,
    interval: int,
    timeout_seconds: int = CODEX_DEVICE_TIMEOUT_SECONDS,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    owns_client = client is None
    client = client or httpx.AsyncClient()
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            response = await client.post(
                CODEX_DEVICE_TOKEN_URL,
                json={"device_auth_id": device_auth_id, "user_code": user_code},
                headers={"User-Agent": "aiuser/1.5.0"},
            )

            if response.is_success:
                data = response.json()
                return await exchange_codex_authorization_code(
                    data["authorization_code"],
                    data["code_verifier"],
                    client=client,
                )

            if response.status_code not in (403, 404):
                response.raise_for_status()

            await asyncio.sleep(interval + CODEX_POLLING_SAFETY_MARGIN_SECONDS)

        raise TimeoutError("Codex device authorization timed out")
    finally:
        if owns_client:
            await client.aclose()


async def exchange_codex_authorization_code(
    code: str,
    code_verifier: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    transport = (
        client._transport
        if client
        and isinstance(getattr(client, "_transport", None), httpx.MockTransport)
        else None
    )
    timeout = client.timeout if client else None
    oauth_client = AsyncOAuth2Client(
        client_id=CODEX_CLIENT_ID,
        token_endpoint_auth_method="none",
        redirect_uri=CODEX_REDIRECT_URI,
        transport=transport,
        timeout=timeout,
    )
    try:
        token = await oauth_client.fetch_token(
            CODEX_OAUTH_TOKEN_URL,
            grant_type="authorization_code",
            code=code,
            code_verifier=code_verifier,
        )
        return dict(token)
    finally:
        await oauth_client.aclose()


async def exchange_codex_refresh_token(
    refresh_token: str, client: Optional[httpx.AsyncClient] = None
) -> Dict[str, Any]:
    transport = (
        client._transport
        if client
        and isinstance(getattr(client, "_transport", None), httpx.MockTransport)
        else None
    )
    timeout = client.timeout if client else None
    oauth_client = AsyncOAuth2Client(
        client_id=CODEX_CLIENT_ID,
        token_endpoint_auth_method="none",
        transport=transport,
        timeout=timeout,
        token={"refresh_token": refresh_token},
    )
    try:
        token = await oauth_client.refresh_token(
            CODEX_OAUTH_TOKEN_URL,
            refresh_token=refresh_token,
        )
        return dict(token)
    finally:
        await oauth_client.aclose()


async def ensure_valid_codex_oauth(
    config: Config,
    force_refresh: bool = False,
    refresh_window_ms: int = 60_000,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    oauth = await get_codex_oauth(config)
    if not oauth or not oauth.get("refresh"):
        raise ValueError("Codex OAuth is not configured")

    access = oauth.get("access")
    expires = int(oauth.get("expires") or 0)
    now = utc_now_ms()
    if not force_refresh and access and expires > (now + refresh_window_ms):
        return oauth

    tokens = await exchange_codex_refresh_token(oauth["refresh"], client=client)
    updated = normalize_codex_tokens(
        tokens,
        previous_account_id=oauth.get("account_id"),
        previous_refresh_token=oauth.get("refresh"),
    )
    await set_codex_oauth(config, updated)
    return updated
