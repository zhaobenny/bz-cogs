from typing import Any, Dict, List

from openai.types.chat import ChatCompletionMessageParam

from aiuser.llm.base import ChatStepResult, LLMProvider
from aiuser.llm.codex.oauth import CODEX_ALLOWED_MODELS
from aiuser.llm.codex.responses import create_codex_response


class CodexProvider(LLMProvider):
    async def list_models(self) -> list[str]:
        return list(CODEX_ALLOWED_MODELS)

    async def create_chat_step(
        self,
        model: str,
        messages: List[ChatCompletionMessageParam],
        kwargs: Dict[str, Any],
    ) -> ChatStepResult:
        content, tool_calls = await create_codex_response(
            self.config,
            model,
            messages,
            kwargs,
        )
        return ChatStepResult(content=content, tool_calls=tool_calls)
