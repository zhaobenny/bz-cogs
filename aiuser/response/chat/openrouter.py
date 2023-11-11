import json
import logging

from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.messages_list.messages import MessagesList
from aiuser.response.chat.generator import Chat_Generator

logger = logging.getLogger("red.bz_cogs.aiuser")


class OpenRouter_Chat_Generator(Chat_Generator):
    def __init__(self, cog: MixinMeta, ctx: commands.Context, messages: MessagesList):
        super().__init__(cog, ctx, messages)

    async def request_openrouter(self, model):
        custom_parameters = await self.config.guild(self.ctx.guild).parameters()
        kwargs = {}

        if custom_parameters is not None:
            custom_parameters = json.loads(custom_parameters)
            kwargs.update(custom_parameters)

        if kwargs.get("logit_bias") is None:
            logit_bias = json.loads(
                await self.config.guild(self.ctx.guild).weights() or "{}"
            )
            kwargs["logit_bias"] = logit_bias

        response = await self.openai_client.chat.completions.with_raw_response.create(
            model=model,
            messages=self.messages,
            **kwargs,
        )

        completion = response.parse()
        completion = completion.choices[0].message.content

        logger.debug(
            f'Generated the following raw response using {model} via OpenRouter in {self.ctx.guild.name}: "{completion}"'
        )
        return completion

    async def generate_message(self):
        model = await self.config.guild(self.ctx.guild).model()

        try:
            logger.debug(
                f"Generating message with prompt: \n{json.dumps(self.messages, indent=4)}"
            )
            response = await self.request_openrouter(model)
            return response
        except:
            logger.error(
                f"Failed API request(s) to OpenRouter. Last exception was:",
                exc_info=True,
            )
            await self.ctx.react_quietly("⚠️")
        return None
