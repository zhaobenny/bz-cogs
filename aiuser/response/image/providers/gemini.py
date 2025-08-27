import base64
import io

import aiohttp
from redbot.core import Config, commands

from aiuser.response.image.providers.generator import ImageGenerator


class GeminiImageGenerator(ImageGenerator):
    def __init__(self, ctx: commands.Context, config: Config, api_key: str = None):

        self.ctx = ctx
        self.config = config
        self.api_key = api_key

    async def _prepare_payload(self, caption):
        return {
            "contents": [
                {
                    "parts": [
                        {"text":  await self.config.guild(self.ctx.guild).image_requests_preprompt() + " " + caption}
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            }
        }

    async def generate_image(self, caption):
        # https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent/

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        payload = await self._prepare_payload(caption)
        url = await self.config.guild(self.ctx.guild).image_requests_endpoint()
        if not url.startswith("https://generativelanguage.googleapis.com/v1beta/models/"):
            raise ValueError("Endpoint is not Google Generative Language API!")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                
                data = await response.json()
                
                try:
                    parts = data["candidates"][0]["content"]["parts"]
                    
                    image_data = None
                    for part in parts:
                        if "inlineData" in part:
                            image_data = part["inlineData"]["data"]
                            break
                    
                    if image_data is None:
                        raise ValueError("No image data found in response")
                                        
                    return io.BytesIO(base64.b64decode(image_data))
                except (KeyError, IndexError) as e:
                    raise ValueError(f"Unable to extract image data from response: {e}")
