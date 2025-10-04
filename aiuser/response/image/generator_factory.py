import logging

from redbot.core import commands, config

from aiuser.config.constants import IMAGE_REQUEST_AIHORDE_URL
from aiuser.response.image.providers.aihorde import AIHordeGenerator
from aiuser.response.image.providers.dalle import DalleImageGenerator
from aiuser.response.image.providers.gemini import GeminiImageGenerator
from aiuser.response.image.providers.generic import GenericImageGenerator
from aiuser.response.image.providers.huggingface import HuggingFaceGenerator
from aiuser.response.image.providers.modal import ModalImageGenerator
from aiuser.response.image.providers.nineteen import NINETEEN_API_URL, NineteenGenerator
from aiuser.response.image.providers.runpod import RunPodGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


async def get_image_generator(ctx: commands.Context, config: config):
    sd_endpoint: str = await config.guild(ctx.guild).image_requests_endpoint()
    if not sd_endpoint:
        logger.error(
            f"Stable Diffusion endpoint not set for {ctx.guild.name}, "
            "disabling Stable Diffusion requests for this server..."
        )
        await config.guild(ctx.guild).image_requests.set(False)
        return None

    if sd_endpoint.startswith("dall-e-"):
        api_key = (await ctx.bot.get_shared_api_tokens("openai")).get("api_key")
        return DalleImageGenerator(ctx, config, sd_endpoint, api_key)
    elif (
        sd_endpoint.startswith("https://huggingface.co/spaces/")
        or ".hf.space" in sd_endpoint
    ):
        return HuggingFaceGenerator(ctx, config, sd_endpoint=sd_endpoint)
    elif sd_endpoint.startswith("https://perchance.org/ai-text-to-image-generator"):
        from aiuser.response.image.providers.perchance import PerchanceGenerator
        return PerchanceGenerator(ctx, config)
    elif sd_endpoint.endswith("imggen.modal.run/"):
        auth_token = (await ctx.bot.get_shared_api_tokens("modal-img-gen")).get("token")
        return ModalImageGenerator(ctx, config, auth_token)
    elif sd_endpoint.startswith(NINETEEN_API_URL):
        return NineteenGenerator(ctx, config)
    elif sd_endpoint.startswith("https://api.runpod.ai/v2/"):
        api_key = (await ctx.bot.get_shared_api_tokens("runpod")).get("apikey")
        return RunPodGenerator(ctx, config, api_key)
    elif sd_endpoint.startswith(IMAGE_REQUEST_AIHORDE_URL):
        api_key = (await ctx.bot.get_shared_api_tokens("aihorde")).get("apikey")
        return AIHordeGenerator(ctx, config, api_key)
    elif sd_endpoint.startswith("https://generativelanguage.googleapis.com/v1beta/models"):
        api_key = (await ctx.bot.get_shared_api_tokens("gemini")).get("apikey") or await ctx.bot.get_shared_api_tokens("openai").get("apikey")
        return GeminiImageGenerator(ctx, config)
    else:
        return GenericImageGenerator(ctx, config)
