import json
import logging

import openai
import openai.error
from redbot.core import commands, Config
from tenacity import (retry, retry_if_exception_type, stop_after_delay,
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


async def generate_response(ctx: commands.Context, config: Config, prompt):
    message = ctx.message
    logger.debug(
        f"Replying to message \"{message.content}\" in {message.guild.name} with prompt: \n{json.dumps(prompt, indent=4)}")
    model = await config.guild(message.guild).model()

    async with ctx.typing():
        try:
            response = await generate_openai_response(model, prompt)
        except openai.error.RateLimitError as e:
            trys = generate_openai_response.retry.statistics["attempt_number"]
            logger.warning(
                f"Failed {trys} API request to OpenAI. You may be ratelimited! Reduce percent chance of reply? See exception from Openai: {e}")
            return await ctx.react_quietly("💤")
        except:
            trys = generate_openai_response.retry.statistics["attempt_number"] or 1
            logger.error(
                f"Failed {trys} API request(s) to OpenAI. Last exception was:", exc_info=True)
            return await ctx.react_quietly("⚠️")

        if (await config.filter_responses()) and is_moderated_response(response, message):
            return await ctx.react_quietly("😶")

        bot_name = message.guild.me.name
        response = response.strip('"')
        response = remove_template_from_response(response, bot_name)
        direct_reply = not ctx.interaction and await is_reply(message)

        if direct_reply:
            return await message.reply(response, mention_author=False)
        else:
            return await ctx.send(response)
