import asyncio
import ipaddress
import json
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver
from yarl import URL


class OutboundURLPolicyError(ValueError):
    pass


class ResponseBodyTooLargeError(ValueError):
    pass


class RestrictedHTTP:
    SCRAPE_TIMEOUT = aiohttp.ClientTimeout(
        total=30,
        connect=10,
        sock_connect=10,
        sock_read=10,
    )
    BODY_READ_TIMEOUT = 5
    MAX_BODY_BYTES = 1 * 1024 * 1024
    SCRAPE_HEADERS = {
        "Cache-Control": "no-cache",
        "Referer": "https://www.google.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    }

    class Resolver(AbstractResolver):
        def __init__(self) -> None:
            self._resolver = aiohttp.resolver.DefaultResolver()

        async def resolve(
            self, hostname: str, port: int = 0, family: int = 0
        ) -> list[dict[str, Any]]:
            records = await self._resolver.resolve(hostname, port, family=family)
            for record in records:
                address = ipaddress.ip_address(str(record["host"]))
                if not address.is_global:
                    raise OutboundURLPolicyError(
                        f"Resolved non-public address for {hostname}: {address}"
                    )
            return records

        async def close(self) -> None:
            await self._resolver.close()

    @classmethod
    def _require_url(cls, raw_url: str) -> None:
        try:
            parsed = urlsplit(str(raw_url).strip())
        except ValueError as exc:
            raise OutboundURLPolicyError("Invalid URL.") from exc

        if parsed.scheme.lower() not in {"http", "https"}:
            raise OutboundURLPolicyError("Only http and https URLs are allowed.")

        hostname = (parsed.hostname or "").strip()
        if not hostname:
            raise OutboundURLPolicyError("URL hostname is required.")

        if parsed.username is not None or parsed.password is not None:
            raise OutboundURLPolicyError(
                "URLs with embedded credentials are not allowed."
            )

        hostname = hostname.rstrip(".").lower()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise OutboundURLPolicyError("Localhost URLs are not allowed.")

        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            return

        raise OutboundURLPolicyError("Direct IP URLs are not allowed.")

    @classmethod
    def _trace_config(cls) -> aiohttp.TraceConfig:
        trace = aiohttp.TraceConfig()

        async def on_request_start(_, __, params) -> None:
            cls._require_url(str(params.url))

        async def on_request_redirect(_, __, params) -> None:
            location = params.response.headers.get(
                "Location"
            ) or params.response.headers.get("URI")
            if not location:
                return
            try:
                target = URL(location)
            except ValueError as exc:
                raise OutboundURLPolicyError("Invalid redirect URL.") from exc
            if not target.scheme:
                target = params.url.join(target)
            cls._require_url(str(target))

        trace.on_request_start.append(on_request_start)
        trace.on_request_redirect.append(on_request_redirect)
        return trace

    @classmethod
    def session(cls, *, headers=None, timeout=None) -> aiohttp.ClientSession:
        if headers is None:
            headers = cls.SCRAPE_HEADERS
        connector = aiohttp.TCPConnector(
            resolver=cls.Resolver(),
            use_dns_cache=False,
        )
        return aiohttp.ClientSession(
            headers=headers,
            connector=connector,
            timeout=timeout or cls.SCRAPE_TIMEOUT,
            trace_configs=[cls._trace_config()],
        )

    @classmethod
    async def _read_limited(cls, response: aiohttp.ClientResponse) -> bytes:
        if (
            response.content_length is not None
            and response.content_length > cls.MAX_BODY_BYTES
        ):
            raise ResponseBodyTooLargeError("Response body too large.")

        chunks = []
        total = 0
        async for chunk in response.content.iter_chunked(8192):
            total += len(chunk)
            if total > cls.MAX_BODY_BYTES:
                raise ResponseBodyTooLargeError("Response body too large.")
            chunks.append(chunk)
        return b"".join(chunks)

    @classmethod
    async def text(cls, response: aiohttp.ClientResponse) -> str:
        raw = await asyncio.wait_for(
            cls._read_limited(response), timeout=cls.BODY_READ_TIMEOUT
        )
        return raw.decode(response.charset or "utf-8", errors="replace")

    @classmethod
    async def json(cls, response: aiohttp.ClientResponse) -> Any:
        return json.loads(await cls.text(response))

    @classmethod
    async def read(cls, response: aiohttp.ClientResponse) -> bytes:
        return await asyncio.wait_for(
            cls._read_limited(response), timeout=cls.BODY_READ_TIMEOUT
        )
