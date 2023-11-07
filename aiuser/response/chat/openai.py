import json
import logging
import random
from datetime import datetime, timedelta

import openai
from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.messages_list.messages import MessagesList
from aiuser.response.chat.generator import Chat_Generator

logger = logging.getLogger("red.bz_cogs.aiuser")


class OpenAI_Chat_Generator(Chat_Generator):
    def __init__(self, cog : MixinMeta, ctx: commands.Context, messages: MessagesList):
        super().__init__(cog, ctx, messages)


    async def request_openai(self, model):
        custom_parameters = await self.config.guild(self.ctx.guild).parameters()
        kwargs = {}

        if custom_parameters is not None:
            custom_parameters = json.loads(custom_parameters)
            kwargs.update(custom_parameters)

        if kwargs.get("logit_bias") is None:
            logit_bias = json.loads(await self.config.guild(self.ctx.guild).weights() or "{}")
            kwargs["logit_bias"] = logit_bias

        if "gpt-4-vision-preview" in model:
            logger.warning("logit_bias is currently not supported for gpt-4-vision-preview, removing...")
            del kwargs["logit_bias"]

        if 'gpt-3.5-turbo-instruct' in model:
            prompt = "\n".join(message['content'] for message in self.messages)
            response = await self.openai_client.completions.with_raw_response.create(
                model=model,
                prompt=prompt,
                **kwargs
            )
            completion = response.parse()
            completion = completion.choices[0].text
        else:
            response = await self.openai_client.chat.completions.with_raw_response.create(
                model=model,
                messages=self.messages,
                **kwargs
            )
            completion = response.parse()
            completion = completion.choices[0].message.content

        await self._update_ratelimit_time(response.headers)
        logger.debug(f"Generated the following raw response using OpenAI in {self.ctx.guild.name}: \"{completion}\"")
        return completion

    async def generate_message(self):
        model = await self.config.guild(self.ctx.guild).model()

        try:
            logger.debug(f"Generating message with prompt: \n{json.dumps(self.messages, indent=4)}")
            response = await self.request_openai(model)
            return response
        except openai.RateLimitError:
            timestamp = datetime.now() + timedelta(seconds=random.randint(32, 35))
            last_reset = datetime.strptime(await self.config.ratelimit_reset(), '%Y-%m-%d %H:%M:%S')
            if last_reset < timestamp:
                await self.config.ratelimit_reset.set(timestamp.strftime('%Y-%m-%d %H:%M:%S'))
            logger.warning(
                f"Failed API request to OpenAI. You are being ratelimited! Recommend adding payment method or to reduce reply percentage. Next reset: {await self.config.ratelimit_reset()}")
            await self.ctx.react_quietly("💤")
        except:
            logger.error(f"Failed API request(s) to OpenAI. Last exception was:", exc_info=True)
            await self.ctx.react_quietly("⚠️")
        return None

    def _extract_time_delta(self, time_str):
        """ for openai's ratelimit time format """

        days, hours, minutes, seconds = 0, 0, 0, 0

        if time_str[-2:] == "ms":
            time_str = time_str[:-2]
            seconds += 1

        components = time_str.split('d')
        if len(components) > 1:
            days = float(components[0])
            time_str = components[1]

        components = time_str.split('h')
        if len(components) > 1:
            hours = float(components[0])
            time_str = components[1]

        components = time_str.split('m')
        if len(components) > 1:
            minutes = float(components[0])
            time_str = components[1]

        components = time_str.split('s')
        if len(components) > 1:
            seconds = float(components[0])
            time_str = components[1]

        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds + random.randint(2, 5))

    async def _update_ratelimit_time(self, response_headers):
        if str(self.openai_client.base_url).startswith("https://api.openai.com/"):
            return

        remaining_requests = response_headers.get("x-ratelimit-remaining-requests") or 1
        remaining_tokens = response_headers.get("x-ratelimit-remaining-tokens") or 1

        timestamp = datetime.now()

        if remaining_requests == 0:
            # x-ratelimit-reset-requests uses per day instead of per minute for free accounts
            request_reset_time = self._extract_time_delta(response_headers.get("x-ratelimit-reset-requests"))
            timestamp = max(timestamp, datetime.now() + request_reset_time)
        elif remaining_tokens == 0:
            tokens_reset_time = self._extract_time_delta(response_headers.get("x-ratelimit-reset-tokens"))
            timestamp = max(timestamp, datetime.now() + tokens_reset_time)

        if remaining_requests == 0 or remaining_tokens == 0:
            await self.config.ratelimit_reset.set(timestamp.strftime('%Y-%m-%d %H:%M:%S'))
