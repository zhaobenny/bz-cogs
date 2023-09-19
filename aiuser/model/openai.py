import json
import logging
import random
from datetime import datetime, timedelta

import aiohttp
import openai
import openai.error
from redbot.core import Config, commands
from tenacity import (retry, retry_if_exception_type, stop_after_delay,
                      wait_random)

from aiuser.model.base import Base_LLM_Response
from aiuser.prompts.common.messagethread import MessageThread

logger = logging.getLogger("red.bz_cogs.aiuser")


class OpenAI_LLM_Response(Base_LLM_Response):
    def __init__(self, ctx: commands.Context, config: Config, prompt: MessageThread):
        super().__init__(ctx, config, prompt)

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

    # temp workaround adapted from here: https://github.com/openai/openai-python/issues/416#issuecomment-1679551808
    async def _update_ratelimit_time(self, _, _1, params: aiohttp.TraceRequestEndParams):
        if not str(params.url).startswith("https://api.openai.com/v1/"):
            return
        response_headers = params.response.headers
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

    @retry(
        retry=(retry_if_exception_type((openai.error.Timeout,
               openai.error.APIConnectionError, openai.error.ServiceUnavailableError))),
        wait=wait_random(min=1, max=3), stop=stop_after_delay(10),
        reraise=True
    )
    async def request_openai(self, model):
        custom_parameters = await self.config.guild(self.ctx.guild).parameters()
        kwargs = {}

        if custom_parameters is not None:
            custom_parameters = json.loads(custom_parameters)
            kwargs.update(custom_parameters)

        if kwargs.get("logit_bias") is None:
            logit_bias = json.loads(await self.config.guild(self.ctx.guild).weights() or "{}")
            kwargs["logit_bias"] = logit_bias

        trace_config = aiohttp.TraceConfig()
        trace_config.on_request_end.append(self._update_ratelimit_time)

        async with aiohttp.ClientSession(trace_configs=[trace_config]) as session:
            openai.aiosession.set(session)

            if 'instruct' in model:
                prompt = "\n".join(message['content'] for message in self.prompt.get_messages())
                response = openai.Completion.create(
                    engine=model,
                    prompt=prompt,
                    **kwargs
                )
                response = response['choices'][0]['text']
            elif 'gpt-3-turbo' in model or 'gpt-4' in model or ('gpt-3.5-turbo' in model and 'instruct' not in model):
                response = openai.ChatCompletion.create(
                    model=model,
                    messages=self.prompt.get_messages(),
                    **kwargs
                )
                response = response["choices"][0]["message"]["content"]

        return response

    async def generate_response(self):
        model = await self.config.guild(self.ctx.guild).model()
        try:
            response = await self.request_openai(model)
            return response
        except openai.error.RateLimitError:
            timestamp = datetime.now() + timedelta(seconds=random.randint(62, 65))
            last_reset = datetime.strptime(await self.config.ratelimit_reset(), '%Y-%m-%d %H:%M:%S')
            if last_reset < timestamp:
                await self.config.ratelimit_reset.set(timestamp.strftime('%Y-%m-%d %H:%M:%S'))
            logger.warning(
                f"Failed API request to OpenAI. You are being ratelimited! Recommend adding payment method or to reduce reply percentage. Next reset: {await self.config.ratelimit_reset()}")
            await self.ctx.react_quietly("💤")
        except:
            trys = self.request_openai.retry.statistics["attempt_number"] or 1
            logger.error(
                f"Failed {trys} API request(s) to OpenAI. Last exception was:", exc_info=True)
            await self.ctx.react_quietly("⚠️")
        return None
