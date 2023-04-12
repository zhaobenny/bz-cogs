import logging
import openai
from ai_user.response.checks import is_moderated_response, is_reply
from ai_user.response.processing import remove_template_from_response
logger = logging.getLogger("red.bz_cogs.ai_user")


async def generate_openai_response(model, prompt):
    try:
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=prompt,
        )
        response = response["choices"][0]["message"]["content"]
    except:
        return logger.error(f"Failed API request to OpenAI", exc_info=True)
    return response


async def generate_response(message, config, prompt):
    model = await config.model()

    response = await generate_openai_response(model, prompt)

    if (not response or (await config.filter_responses()) and is_moderated_response(response, message)):
        return (False, "😶")

    bot_name = message.guild.me.name
    response = response.strip('"')
    response = remove_template_from_response(response, bot_name)
    direct_reply = await is_reply(message)

    return (direct_reply, response)
