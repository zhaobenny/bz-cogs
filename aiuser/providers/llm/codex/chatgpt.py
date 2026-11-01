from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from authlib.jose import JsonWebToken
from redbot.core import Config
from redbot.core.data_manager import core_data_path

CODEX_ENDPOINT_MODE = "codex"


async def is_codex_endpoint_mode(config: Config) -> bool:
    return await config.custom_openai_endpoint() == CODEX_ENDPOINT_MODE


def secure_token_store_permissions():
    path = core_data_path() / "settings.json"
    if path.exists():
        os.chmod(path, 0o600)


ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
REDIRECT = "http://127.0.0.1:1455/auth/callback"
SERVICE = "aiuser_chatgpt"
_REFRESH_LOCK = asyncio.Lock()


async def load(bot):
    return json.loads((await bot.get_shared_api_tokens(SERVICE)).get("oauth", "{}"))


async def save(bot, data):
    await bot.set_shared_api_tokens(SERVICE, oauth=json.dumps(data))
    secure_token_store_permissions()


async def start(bot, new_account=False):
    saved = await load(bot)
    host = saved.get("host") or "urn:uuid:" + str(uuid.uuid4())
    if not saved.get("host"):
        await save(bot, {**saved, "host": host})
    verifier = secrets.token_urlsafe(64)
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    params = {
        "client_id": "dynamic_agent_client",
        "agent_name_hint": "aiuser",
        "ext_agent_host_id": host,
        "response_type": "code",
        "redirect_uri": REDIRECT,
        "scope": "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
        "resource": RESOURCE,
        "state": state,
        "nonce": nonce,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }
    if saved.get("client_id") and not new_account:
        params["client_id"] = saved["client_id"]
        params.pop("agent_name_hint")
    return ISSUER + "/api/accounts/authorize?" + urlencode(params), {
        "state": state,
        "nonce": nonce,
        "verifier": verifier,
        "host": host,
        "client_id": None if new_account else saved.get("client_id"),
        "subject": None if new_account else saved.get("subject"),
    }


async def finish(bot, pending, callback):
    parsed = urlsplit(callback.strip())
    if (parsed.scheme, parsed.netloc, parsed.path, parsed.fragment) != (
        "http",
        "127.0.0.1:1455",
        "/auth/callback",
        "",
    ):
        raise ValueError("Invalid callback URL")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if any(len(values) != 1 for values in query.values()) or not secrets.compare_digest(
        query.get("state", [""])[0], pending["state"]
    ):
        raise ValueError("Invalid callback state")
    client_id = query.get("client_id", [pending.get("client_id") or ""])[0]
    if (
        query.get("error")
        or not query.get("code", [""])[0]
        or not client_id
        or client_id == "dynamic_agent_client"
        or (pending.get("client_id") and client_id != pending["client_id"])
    ):
        raise ValueError("Authorization was not completed")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            ISSUER + "/api/accounts/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": query["code"][0],
                "code_verifier": pending["verifier"],
                "redirect_uri": REDIRECT,
                "resource": RESOURCE,
            },
        )
        response.raise_for_status()
        token = response.json()
        response = await client.get(ISSUER + "/.well-known/jwks.json")
        response.raise_for_status()
        claims = JsonWebToken(["RS256"]).decode(
            token["id_token"],
            response.json(),
            claims_options={
                "iss": {"essential": True, "value": ISSUER},
                "aud": {"essential": True, "value": client_id},
                "exp": {"essential": True},
                "sub": {"essential": True},
                "nonce": {"essential": True, "value": pending["nonce"]},
            },
        )
        claims.validate()
        if pending.get("subject") and claims["sub"] != pending["subject"]:
            raise ValueError("ChatGPT account changed")
        if (
            "chatgpt.tokens.use.direct" not in token.get("scope", "").split()
            or not token.get("refresh_token")
            or not token.get("access_token")
        ):
            raise ValueError("ChatGPT plan permission was not granted")
        response = await client.get(
            RESOURCE + "/models",
            headers={"Authorization": "Bearer " + token["access_token"]},
        )
        response.raise_for_status()
        models = [
            m["slug"]
            for m in response.json()["models"]
            if m.get("visibility") == "list" and m.get("slug")
        ]
        if not models:
            raise ValueError("No ChatGPT models are available")
    await save(
        bot,
        {
            "host": pending["host"],
            "client_id": client_id,
            "subject": claims["sub"],
            "email": claims.get("email"),
            "id_token": token["id_token"],
            "access": token["access_token"],
            "refresh": token["refresh_token"],
            "scope": token["scope"],
            "expires": time.time() + int(token.get("expires_in", 3600)),
        },
    )
    return models


async def valid(bot, client, force=False):
    async with _REFRESH_LOCK:
        return await _valid_locked(bot, client, force)


async def _valid_locked(bot, client, force=False):
    data = await load(bot)
    if not data.get("client_id") or not data.get("refresh"):
        raise ValueError("Sign in with ChatGPT first")
    if not force and data.get("access") and data.get("expires", 0) > time.time() + 60:
        return data
    response = await client.post(
        ISSUER + "/api/accounts/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": data["client_id"],
            "refresh_token": data["refresh"],
            "resource": RESOURCE,
        },
    )
    response.raise_for_status()
    token = response.json()
    scope = token.get("scope", data["scope"])
    if "chatgpt.tokens.use.direct" not in scope.split() or not token.get(
        "access_token"
    ):
        raise ValueError("ChatGPT plan permission is missing")
    data.update(
        access=token["access_token"],
        refresh=token.get("refresh_token", data["refresh"]),
        expires=time.time() + int(token.get("expires_in", 3600)),
        scope=scope,
    )
    await save(bot, data)
    return data
