import asyncio
import logging
import random
import re
from datetime import datetime, timezone

from discord import AllowedMentions
from redbot.core import Config, commands

from aiuser.utils.constants import REGEX_RUN_TIMEOUT
from aiuser.utils.utilities import to_thread
from aiuser.response.chat.generator import ChatGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")



class ChatResponse():
    def __init__(self, ctx: commands.Context, config: Config, chat: ChatGenerator):
        self.ctx = ctx
        self.config = config
        self.response = None
        self.chat = chat
        self.can_reply = chat.can_reply

    async def send(self):
        message = self.ctx.message

        self.response = await self.chat.generate_message()

        if not self.response:
            return False

        await self.remove_patterns_from_response()

        if not self.response:
            return False

        allowed_mentions = AllowedMentions(everyone=False, roles=False, users=[message.author])

        if len(self.response) >= 2000:
            chunks = [self.response[i:i + 2000]
                      for i in range(0, len(self.response), 2000)]
            for chunk in chunks:
                await self.ctx.send(chunk, allowed_mentions=allowed_mentions)
        elif self.can_reply and await self.is_reply():
            await message.reply(self.response, mention_author=False, allowed_mentions=allowed_mentions)
        elif self.ctx.interaction:
            await self.ctx.interaction.followup.send(self.response, allowed_mentions=allowed_mentions)
        else:
            await self.ctx.send(self.response, allowed_mentions=allowed_mentions)
        return True

    async def remove_patterns_from_response(self) -> str:

        @to_thread(timeout=REGEX_RUN_TIMEOUT)
        def substitute(pattern: re.Pattern, response):
            response = (pattern.sub('', response))
            return response

        @to_thread(timeout=REGEX_RUN_TIMEOUT)
        def compile(pattern: re.Pattern):
            return re.compile(pattern)

        patterns = await self.config.guild(self.ctx.guild).removelist_regexes()

        botname = self.ctx.message.guild.me.nick or self.ctx.bot.user.display_name
        patterns = [pattern.replace(r'{botname}', botname)
                    for pattern in patterns]

        # get last 10 authors and applies regex patterns with display name
        authors = set()
        async for m in self.ctx.channel.history(limit=10):
            if m.author != self.ctx.guild.me:
                authors.add(m.author.display_name)

        authorname_patterns = list(
            filter(lambda pattern: r'{authorname}' in pattern, patterns))
        patterns = [
            pattern for pattern in patterns if r'{authorname}' not in pattern]

        for pattern in authorname_patterns:
            for author in authors:
                patterns.append(pattern.replace(r'{authorname}', author))

        complied_patterns = []
        for pattern in patterns:
            try:
                complied_patterns.append(await compile(pattern))
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timed out after {REGEX_RUN_TIMEOUT} seconds while compiling regex pattern \"{pattern}\", continuing...")
            except Exception:
                logger.warning(
                    f"Failed to compile regex pattern \"{pattern}\" for response \"{self.response}\", continuing...", exc_info=True)

        response = self.response
        response = response.strip(' \n')

        for pattern in complied_patterns:
            try:
                response = await substitute(pattern, response)
                response = response.strip(' \n')
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timed out after {REGEX_RUN_TIMEOUT} seconds while applying regex pattern \"{pattern.pattern}\" in response \"{self.response}\" \
                        Please check the regex pattern for catastrophic backtracking. Continuing...")

        self.response = response

    async def is_reply(self):
        if self.ctx.interaction:
            return False

        message = self.ctx.message
        try:
            await self.ctx.fetch_message(message.id)
        except Exception:
            return False

        time_diff = datetime.now(timezone.utc) - message.created_at

        if time_diff.total_seconds() > 8 or random.random() < 0.25:
            return True

        try:
            async for last_message in message.channel.history(limit=1):
                if last_message.author == message.guild.me:
                    return True
        except Exception:
            pass

        return False
