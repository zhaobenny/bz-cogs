import json
import logging
from redbot.core import commands, Config

from ai_user.prompts.common.messages_list import MessagesList
from ai_user.response.common.checks import is_moderated_response, is_reply
from ai_user.response.common.processing import remove_patterns_from_response
import google.generativeai as palm

logger = logging.getLogger("red.bz_cogs.ai_user")


def adapt_for_palm(prompt: MessagesList):
    request_json = {
        "instances": [{
            "context":  "CONTEXT",
            "examples": [
            ],
            "messages": [
            ],
        }],
    }
    messages = prompt.get_messages()

    # temp, make better later on
    for message in messages:
        if message["role"] == "system":
            request_json["instances"][0]["context"] = message["content"]
            messages.remove(message)
            break
    for message in messages:
        request_json["instances"][0]["messages"].append({
            "author": "user" if message["role"] == "user" else "bot",
            "content": message["content"],
        })

    return request_json


async def generate_response(ctx: commands.Context, config: Config, prompt: MessagesList):
    message = ctx.message

    debug_content = f'"{message.content}"' if message.content else ""
    request_json = adapt_for_palm(prompt)
    logger.debug(
        f"Replying to message {debug_content} in {message.guild.name} with prompt: \n{json.dumps(request_json, indent=4)}")
    response = "Test"

    if (await config.guild(ctx.guild).filter_responses()) and is_moderated_response(response, message):
        return await ctx.react_quietly("😶")

    bot_name = message.guild.me.name
    response = remove_patterns_from_response(response, bot_name)
    should_direct_reply = not ctx.interaction and await is_reply(message)

    if should_direct_reply:
        return await message.reply(response, mention_author=False)
    else:
        return await ctx.send(response)
