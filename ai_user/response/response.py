import logging
import openai
from ai_user.response.checks import is_moderated_response, is_reply
from ai_user.response.processing import remove_template_from_response
logger = logging.getLogger("red.bz_cogs.ai_user")


async def generate_response(message, config, prompt, bot_name):
    model = await config.model()
    async with message.channel.typing():
        try:
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=prompt,
            )
            response = response["choices"][0]["message"]["content"]
        except:
            return logger.error(f"Failed API request to OpenAI", exc_info=True)

    if (await config.filter_responses()) and is_moderated_response(response, message):
        return (False, "😶")

    response = remove_template_from_response(response, bot_name)

    direct_reply = is_reply(message)

    return (direct_reply, response)
