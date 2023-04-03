import datetime
import logging
import random

logger = logging.getLogger("red.bz_cogs.ai_user")

def is_moderated_response(response, message):
    """ filters out responses that were moderated out """
    response = response.lower()
    filters = ["language model", "openai", "sorry", "apologize"]

    if any(filter in response for filter in filters):
        logger.debug(
            f"Filtered out canned response replying to \"{message.content}\" in {message.guild.name}: \n{response}")
        return True

    return False

def is_reply(message):
        time_diff = datetime.datetime.utcnow() - message.created_at
        if time_diff.total_seconds() > 8:
            return True
        if (random.random() < 0.25):
            return True

        return False
