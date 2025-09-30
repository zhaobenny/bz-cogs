from aiuser.functions.imagerequest.providers.util import fetch_image_bytes


async def generate(description, request, _=None):  # endpoint unused
    r = await request.openai_client.images.generate(
        model="gpt-image-1", prompt=description, quality="standard", n=1, size="1024x1024", response_format="url",
    )
    return await fetch_image_bytes(r.data[0].url)