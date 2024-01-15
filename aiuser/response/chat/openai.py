import json
import logging

import httpx
import openai
from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.common.constants import VISION_SUPPORTED_MODELS
from aiuser.messages_list.messages import MessagesList
from aiuser.response.chat.generator import Chat_Generator

logger = logging.getLogger("red.bz_cogs.aiuser")


class OpenAI_API_Generator(Chat_Generator):
    def __init__(self, cog: MixinMeta, ctx: commands.Context, messages: MessagesList):
        super().__init__(cog, ctx, messages)

    async def get_custom_parameters(self):
        custom_parameters = await self.config.guild(self.ctx.guild).parameters()
        kwargs = {}

        if custom_parameters is not None:
            custom_parameters = json.loads(custom_parameters)
            kwargs.update(custom_parameters)

        if kwargs.get("logit_bias") is None:
            logit_bias = json.loads(await self.config.guild(self.ctx.guild).weights() or "{}")
            kwargs["logit_bias"] = logit_bias

        if self.model in VISION_SUPPORTED_MODELS:
            logger.warning(f"logit_bias is currently not supported for for model {self.model}, removing...")
            del kwargs["logit_bias"]
            if kwargs.get("max_tokens") is None:
                kwargs["max_tokens"] = 500

        return kwargs

    async def request_openai(self):
        kwargs = await self.get_custom_parameters()

        if "gpt-3.5-turbo-instruct" in self.model:
            prompt = "\n".join(message["content"] for message in self.messages)
            response = await self.openai_client.completions.create(
                model=self.model, prompt=prompt, **kwargs
            )
            completion = response.choices[0].message.content
        else:
            response = (
                await self.openai_client.chat.completions.create(
                    model=self.model, messages=self.messages, **kwargs
                )
            )

            if hasattr(response, "error"):
                raise Exception(f"LLM endpoint error: {response.error}")

            completion = response.choices[0].message.content

        logger.debug(
            f'Generated the following raw response in {self.ctx.guild.name}: "{completion}"'
        )
        return completion

    async def generate_message(self):
        try:
            response = await self.request_openai()
            return response
        except httpx.ReadTimeout:
            logger.error(f"Failed request to LLM endpoint. Timed out after >50 seconds")
            await self.ctx.react_quietly("💤")
        except openai.RateLimitError:
            await self.ctx.react_quietly("💤")
        except:
            logger.exception(f"Failed API request(s) to LLM endpoint")
            await self.ctx.react_quietly("⚠️")
        return None
