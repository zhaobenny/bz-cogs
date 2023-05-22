import json
import logging
import random
import re
from datetime import datetime, timezone

from redbot.core import Config, commands

from ai_user.prompts.common.messages_list import MessagesList


logger = logging.getLogger("red.bz_cogs.ai_user")


class Base_LLM_Response():
    def __init__(self, ctx: commands.Context, config: Config, prompt: MessagesList):
        self.ctx = ctx
        self.config = config
        self.prompt = prompt
        self.response = None

    async def generate_response(self):
        raise NotImplementedError

    async def sent_response(self):
        message = self.ctx.message

        debug_content = f'"{message.content}"' if message.content else ""
        logger.debug(
            f"Replying to message {debug_content} in {message.guild.name} with prompt: \n{json.dumps(self.prompt.get_messages(), indent=4)}")

        async with self.ctx.typing():
            self.response = await self.generate_response()

        if not self.response:
            return

        if (await self.config.guild(self.ctx.guild).filter_responses()) and self.check_if_response_blocked():
            await self.ctx.react_quietly("😶")
        self.remove_patterns_from_response()
        if self.check_blacklist_patterns():
            logger.debug(
                f"Filtered out canned response replying to \"{self.ctx.message.content}\" in {self.ctx.message.content}: \n{self.response}")
            await self.ctx.react_quietly("😶")
            return
        should_direct_reply = not self.ctx.interaction and await self.is_reply()

        if should_direct_reply:
            return await message.reply(self.response, mention_author=False)
        else:
            return await self.ctx.send(self.response)

    def remove_patterns_from_response(self) -> str:
        bot_member = self.ctx.message.guild.me
        patterns = [
            rf'^(User )?"?{bot_member.name}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
            rf'^As "?{bot_member.name}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
            rf'^[<({{\[]{bot_member.name}[>)}}\]]',  # [name], {name}, <name>, (name)
            rf'^{bot_member.name}:',
            rf'^(User )?"?{bot_member.nick}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
            rf'^As "?{bot_member.nick}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
            rf'^[<({{\[]{bot_member.nick}[>)}}\]]',  # [name], {name}, <name>, (name)
            rf'^{bot_member.nick}:',
        ]
        response = self.response.strip(' "')
        for pattern in patterns:
            response = re.sub(pattern, '', response).strip(' \n":')
            if response.count('"') == 1:
                response = response.replace('"', '')
        self.response = response

    def check_if_response_blocked(self):
        """ filters out responses that are wooden """

        response = self.response.lower()
        filters = ["language model", "openai"]

        if any(match in response for match in filters):
            return True

        return False

    async def is_reply(self):
        message = self.ctx.message
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
