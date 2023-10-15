import asyncio
import json
import logging
import random
import re
from datetime import datetime, timezone

from redbot.core import Config, commands

from aiuser.prompts.common.messagethread import MessageThread

logger = logging.getLogger("red.bz_cogs.aiuser")


class Base_LLM_Response():
    def __init__(self, ctx: commands.Context, config: Config, prompt: MessageThread):
        self.ctx = ctx
        self.config = config
        self.prompt = prompt
        self.response = None

    async def _is_message_exists(self, id):
        try:
            await self.ctx.fetch_message(id)
            return True
        except:
            return False

    async def generate_response(self):
        raise NotImplementedError

    async def sent_response(self, standalone=False):
        message = self.ctx.message

        if not standalone:
            debug_content = f'"{message.content}"' if message.content else ""
            logger.debug(
                f"Replying to message {debug_content} in {message.guild.name} with prompt: \n{json.dumps(self.prompt.get_messages(), indent=4)}")
        else:
            logger.debug(
                f"Generating message with prompt: \n{json.dumps(self.prompt.get_messages(), indent=4)}")

        async with self.ctx.typing():
            self.response = await self.generate_response()

        if not self.response:
            return

        await self.remove_patterns_from_response()

        should_direct_reply = not self.ctx.interaction and await self.is_reply()

        if len(self.response) >= 2000:
            chunks = [self.response[i:i+2000] for i in range(0, len(self.response), 2000)]
            for chunk in chunks:
                await self.ctx.send(chunk)
        elif should_direct_reply and not standalone and await self._is_message_exists(message.id):
            await message.reply(self.response, mention_author=False)
        else:
            await self.ctx.send(self.response)

    async def remove_patterns_from_response(self) -> str:
        async def sub_with_timeout(pattern: re.Pattern, response):
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(lambda: pattern.sub('', response).strip(' \n":')),
                    timeout=5
                )
                return result
            except asyncio.TimeoutError:
                logger.error(f"Timed out while applying regex pattern: {pattern.pattern}")
                return response

        patterns = await self.config.guild(self.ctx.guild).removelist_regexes()

        botname = self.ctx.message.guild.me.nick or self.ctx.bot.user.display_name
        patterns = [pattern.replace(r'{botname}', botname) for pattern in patterns]

        # get last 10 authors and applies regex patterns with display name
        authors = set()
        async for m in self.ctx.channel.history(limit=10):
            if m.author != self.ctx.guild.me:
                authors.add(m.author.display_name)

        authorname_patterns = list(filter(lambda pattern: r'{authorname}' in pattern, patterns))
        patterns = [pattern for pattern in patterns if r'{authorname}' not in pattern]

        for pattern in authorname_patterns:
            for author in authors:
                patterns.append(pattern.replace(r'{authorname}', author))

        patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

        response = self.response.strip(' "')
        for pattern in patterns:
            response = await sub_with_timeout(pattern, response)
            if response.count('"') == 1:
                response = response.replace('"', '')
        self.response = response

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
