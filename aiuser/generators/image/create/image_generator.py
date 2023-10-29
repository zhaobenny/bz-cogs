from redbot.core import Config, commands

class ImageGenerator:
    def __init__(self, ctx: commands.Context, config: Config):
        self.ctx = ctx
        self.config = config

    async def generate_image(self, _):
        raise NotImplementedError
