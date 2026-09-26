from typing import Any

from openai.types.chat import ChatCompletionMessageParam
from redbot.core.bot import Red

from aiuser.providers.llm.base import ChatStepResult, LLMProvider
from aiuser.providers.llm.codex.oauth import CODEX_ALLOWED_MODELS
from aiuser.providers.llm.codex.responses import create_codex_response


class CodexProvider(LLMProvider):
    def __init__(self, config, bot: Red):
        super().__init__(config)
        self.bot = bot

    async def list_models(self) -> list[str]:
        return list(CODEX_ALLOWED_MODELS)

    async def create_chat_step(
        self,
        model: str,
        messages: list[ChatCompletionMessageParam],
        kwargs: dict[str, Any],
    ) -> ChatStepResult:
        content, tool_calls = await create_codex_response(
            self.bot,
            self.config,
            model,
            messages,
            kwargs,
        )
        return ChatStepResult(content=content, tool_calls=tool_calls)
