from typing import Any

import httpx
from openai.types.chat import ChatCompletionMessageParam
from redbot.core.bot import Red

from aiuser.providers.llm.base import ChatStepResult, LLMProvider
from aiuser.providers.llm.codex.chatgpt import RESOURCE, valid
from aiuser.providers.llm.codex.responses import create_codex_response


class CodexProvider(LLMProvider):
    def __init__(self, config, bot: Red):
        super().__init__(config)
        self.bot = bot

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=30) as client:
            oauth = await valid(self.bot, client)
            response = await client.get(
                RESOURCE + "/models",
                headers={"Authorization": "Bearer " + oauth["access"]},
            )
            response.raise_for_status()
            return [
                m["slug"]
                for m in response.json()["models"]
                if m.get("visibility") == "list" and m.get("slug")
            ]

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
