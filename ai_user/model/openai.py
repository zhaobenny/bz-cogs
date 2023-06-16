import json
import logging
import openai
import openai.error
from redbot.core import commands, Config
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_random_exponential
from ai_user.model.base import Base_LLM_Response
from ai_user.prompts.common.messages_list import MessagesList


logger = logging.getLogger("red.bz_cogs.ai_user")


class OpenAI_LLM_Response(Base_LLM_Response):
    def __init__(self, ctx: commands.Context, config: Config, prompt: MessagesList):
        super().__init__(ctx, config, prompt)

    @retry(
        retry=(retry_if_exception_type((openai.error.Timeout, openai.error.APIConnectionError, openai.error.RateLimitError))),
        wait=wait_random_exponential(min=1, max=5), stop=stop_after_delay(12),
        reraise=True
    )
    async def request_openai(self, model):
        custom_parameters = await self.config.guild(self.ctx.guild).parameters()
        kwargs = {}

        if custom_parameters is not None:
            custom_parameters = json.loads(custom_parameters)
            kwargs.update(custom_parameters)

        if kwargs.get("logit_bias") is None:
            logit_bias = json.loads(await self.config.guild(self.ctx.guild).weights())
            kwargs["logit_bias"] = logit_bias

        response = await openai.ChatCompletion.acreate(
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
        except openai.error.RateLimitError as e:
            trys = self.request_openai.retry.statistics["attempt_number"]
            logger.warning(
                f"Failed {trys} API request to OpenAI. You may be ratelimited! Reduce percent chance of reply? See exception from Openai: {e}")
            await self.ctx.react_quietly("💤")
        except:
            trys = self.request_openai.retry.statistics["attempt_number"] or 1
            logger.error(
                f"Failed {trys} API request(s) to OpenAI. Last exception was:", exc_info=True)
            await self.ctx.react_quietly("⚠️")
        return None
