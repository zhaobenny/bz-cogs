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
        retry=(retry_if_exception_type(openai.error.Timeout) | retry_if_exception_type(
            openai.error.APIConnectionError) | retry_if_exception_type(openai.error.RateLimitError)),
        wait=wait_random_exponential(min=1, max=5), stop=stop_after_delay(10),
        reraise=True
    )
    async def request_openai(self, model):
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=self.prompt.get_messages(),
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
