import json
from redbot.core import Config, commands

class ImageGenerator:
    def __init__(self, ctx: commands.Context, config: Config):
        self.ctx = ctx
        self.config = config

    async def _prepare_payload(self, caption):
        parameters = await self.config.guild(self.ctx.guild).image_requests_parameters()
        payload = json.loads(parameters) if parameters else {}
        prompt = (
            await self.config.guild(self.ctx.guild).image_requests_preprompt()
            + " "
            + caption
        )
        payload["prompt"] = prompt
        return payload

    async def generate_image(self, _):
        raise NotImplementedError
