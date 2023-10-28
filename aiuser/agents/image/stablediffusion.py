import base64
import io

import aiohttp
import discord
import openai


async def is_image_request(message: discord.Message):
    botname = message.guild.me.nick or message.guild.me.display_name
    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
                "content": f"Think step by step. Youa are {botname}. Is the following a full message asking for a picture, image, or picture of yourself? Answer with True/False"},
            {"role": "user", "content": message.content}
        ],
        max_tokens=1,
    )
    bool_response = response["choices"][0]["message"]["content"]
    return bool_response == "True"


async def send_image(message):
    caption = await create_image_caption(message)
    await message.channel.send(f"Caption: {caption}")
    if caption is None:
        return False

    image = await generate_image(caption)
    await message.channel.send(file=discord.File(image, filename="me.png"))
    return True


# https://www.reddit.com/r/StableDiffusion/comments/11g9zul/using_chatgpt_as_a_prompt_generator_wexample/
system = """
I want you to act as a Stable Diffusion Art Prompt Generator. The formula for a prompt is made of parts, the parts are indicated by brackets. The [Subject] is the person place or thing the image is focused on. [Emotions] is the emotional look the subject or scene might have. [Verb] is What the subject is doing, such as standing, jumping, working and other varied that match the subject. [Adjectives] like beautiful, rendered, realistic, tiny, colorful and other varied that match the subject. The [Environment] in which the subject is in, [Lighting] of the scene like moody, ambient, sunny, foggy and others that match the Environment and compliment the subject. [Photography type] like Polaroid, long exposure, monochrome, GoPro, fisheye, bokeh and others. And [Quality] like High definition, 4K, 8K, 64K UHD, SDR and other. The subject and environment should match and have the most emphasis.
It is ok to omit one of the other formula parts. I will give you a [Subject], you will respond with a full prompt. Present the result as one full sentence, no line breaks, no delimiters, and keep it as concise as possible while still conveying a full scene.

Here is a sample of how it should be output: "Beautiful woman, contemplative and reflective, sitting on a bench, cozy sweater, autumn park with colorful leaves, soft overcast light, muted color photography style, 4K quality."

Convert the below message to a Stable Diffusion Art Prompt.  The prompt should be a full sentence, no second person references, no line breaks, no delimiters, and keep it as concise as possible while still conveying a full scene.
"""


async def create_image_caption(message: discord.Message):
    request = message.content.replace("yourself", "katsuragi misato")
    request = request.replace("you", "katsuragi misato")

    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": request}
        ],
    )
    prompt = response["choices"][0]["message"]["content"].lower()
    if "sorry" in prompt:
        return None
    return prompt


async def generate_image(caption):
    url = "https://mature-mazda-windows-fits.trycloudflare.com"

    payload = {
        "prompt": caption,
        "negative_prompt": "worst quality, low quality:1.4",
        "sampler_name": "Euler a",
        "steps": 20,
        "denoising_strength": 0.5,
        "cfg": 5
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url=f'{url}/sdapi/v1/txt2img', json=payload) as response:
            r = await response.json()

    image = (io.BytesIO(base64.b64decode(r['images'][0])))
    return image
