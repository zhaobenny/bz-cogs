import logging

import openai
import openai.error
from tenacity import (RetryError, retry, retry_if_exception, stop_after_delay,
                      wait_random_exponential)

from ai_user.response.checks import is_moderated_response, is_reply
from ai_user.response.processing import remove_template_from_response

logger = logging.getLogger("red.bz_cogs.ai_user")


@retry(retry=(retry_if_exception(openai.error.Timeout) | retry_if_exception(openai.error.APIConnectionError) | retry_if_exception(openai.error.RateLimitError)), wait=wait_random_exponential(min=1, max=10), stop=stop_after_delay(10))
async def generate_openai_response(model, prompt):
    response = await openai.ChatCompletion.acreate(
        model=model,
        messages=prompt,
    )
    response = response["choices"][0]["message"]["content"]
    return response


async def generate_response(message, config, prompt):
    model = await config.model()

    try:
        response = await generate_openai_response(model, prompt)
    except RetryError:
        trys = generate_openai_response.retry.statistics["attempt_number"]
        logger.error(
            f"Failed {trys} API requests to OpenAI. The last exception was:", exc_info=True)
        return (False, "😶")
    except:
        logger.error(
            "Failed API request to OpenAI. The exception was:", exc_info=True)
        return (False, "😶")

    if (await config.filter_responses()) and is_moderated_response(response, message):
        return (False, "😶")

    bot_name = message.guild.me.name
    response = response.strip('"')
    response = remove_template_from_response(response, bot_name)
    direct_reply = await is_reply(message)

    return (direct_reply, response)
