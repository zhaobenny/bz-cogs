from aiuser.functions.imagerequest.providers.util import fetch_image_bytes


async def generate(description, request, _):
    model = await request.config.guild(request.ctx.guild).function_calling_image_model() or "gpt-image-1"
    r = await request.openai_client.images.generate(model=model, prompt=description, quality="standard", n=1, size="1024x1024", response_format="url")
    return await fetch_image_bytes(r.data[0].url)