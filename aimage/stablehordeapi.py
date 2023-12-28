# https://github.com/F1zzTao/StableHordeAPI.py/blob/main/stablehorde_api/client.py
import json
from typing import Optional

import aiohttp


class StableHordeAPI:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: Optional[str] = None,
        api: Optional[str] = 'https://stablehorde.net/api/v2',
    ):
        self._session: aiohttp.ClientSession = session
        self.api_key: str = api_key
        self.api: str = api

    async def _request(self, url: str, method: str = 'GET', json=None, headers=None) -> aiohttp.ClientResponse:
        """Request an url using choiced method"""
        response = await self._session.request(method, url, json=json, headers=headers)
        return response

    async def txt2img_request(self, payload: dict) -> dict:
        """Create an asynchronous request to generate images"""
        response = await self._request(
            self.api+'/generate/async', "POST", payload, {'apikey': self.api_key}
        )
        return json.loads(await response.content.read())

    async def generate_check(self, uuid: str) -> dict:
        """Check the status of generation without consuming bandwidth"""
        response = await self._request(
            self.api+f'/generate/check/{uuid}'
        )
        if response.status == 404:
            raise ValueError("You entered an UUID that is not found")

        return json.loads(await response.content.read())

    async def generate_status(self, uuid: str) -> dict:
        """
        Same as `generate_check`, but will also include all already
        generated images in a base64 encoded .webp files (if r2 not set).
        You should not request this often. It's limited to 1 request per minute
        """
        response = await self._request(
            self.api+f'/generate/status/{uuid}'
        )
        if response.status == 404:
            raise ValueError("You entered an UUID that is not found")

        return json.loads(await response.content.read())
