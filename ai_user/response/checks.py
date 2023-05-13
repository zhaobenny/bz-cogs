import logging
import random
from datetime import datetime, timezone

logger = logging.getLogger("red.bz_cogs.ai_user")

def is_moderated_response(response, message):
    """ filters out responses that were moderated out """
    response = response.lower()
    filters = ["language model", "openai", "sorry"]

    if any(match in response for match in filters):
        logger.debug(
            f"Filtered out canned response replying to \"{message.content}\" in {message.guild.name}: \n{response}")
        return True

    return False

async def is_reply(message):
    time_diff = datetime.now(timezone.utc) - message.created_at
    if time_diff.total_seconds() > 8:
        return True
    if random.random() < 0.25:
        return True
    try:
        last_message = [m async for m in message.channel.history(limit=1)]
        if last_message[0].author == message.guild.me:
            return True
    except:
        pass
    return False
