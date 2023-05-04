import json
import logging

import openai
import openai.error
from tenacity import (RetryError, retry, retry_if_exception_type, stop_after_delay,
                      wait_random_exponential)

from ai_user.response.checks import is_moderated_response, is_reply
from ai_user.response.processing import remove_template_from_response

logger = logging.getLogger("red.bz_cogs.ai_user")


@retry(
    retry=(retry_if_exception_type(openai.error.Timeout) | retry_if_exception_type(
        openai.error.APIConnectionError) | retry_if_exception_type(openai.error.RateLimitError)),
    wait=wait_random_exponential(min=1, max=5), stop=stop_after_delay(10),
    reraise=True
)
async def generate_openai_response(model, prompt):
    response = await openai.ChatCompletion.acreate(
        model=model,
        messages=prompt,
    )
    response = response["choices"][0]["message"]["content"]
    return response


async def generate_response(message, config, prompt):
    logger.debug(
        f"Replying to message \"{message.content}\" in {message.guild.name} with prompt: \n{json.dumps(prompt, indent=4)}")
    model = await config.model()

    try:
        response = await generate_openai_response(model, prompt)
    except openai.error.RateLimitError:
        trys = generate_openai_response.retry.statistics["attempt_number"]
        logger.warning(
            f"Failed {trys} API request to OpenAI. You are being ratelimited, switch to a paid account or reduce percent chance of reply. Last exception was:", exc_info=True)
        return await message.add_reaction("💤")
    except:
        trys = generate_openai_response.retry.statistics["attempt_number"] or 1
        logger.error(
            f"Failed {trys} API request to OpenAI. Last exception was:", exc_info=True)
        return await message.add_reaction("⚠️")

    if (await config.filter_responses()) and is_moderated_response(response, message):
        return await message.add_reaction("😶")

    async with message.channel.typing():
        bot_name = message.guild.me.name
        response = response.strip('"')
        response = remove_template_from_response(response, bot_name)
        direct_reply = await is_reply(message)

        if direct_reply:
            return await message.reply(response, mention_author=False)
        else:
            return await message.channel.send(response)
