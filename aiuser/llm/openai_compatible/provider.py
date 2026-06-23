from typing import Any, Dict, List

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCall,
)
from redbot.core import Config

from aiuser.llm.base import ChatStepResult, LLMProvider
from aiuser.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_kind,
)

ASSISTANT_EXTRA_FIELD_NAMES = ("reasoning", "reasoning_details")


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, config: Config, openai_client: AsyncOpenAI):
        super().__init__(config)
        self.openai_client = openai_client

    async def list_models(self) -> list[str]:
        res = await self.openai_client.models.list()
        endpoint_kind = get_openai_compat_kind(
            await self.config.custom_openai_endpoint()
        )

        if endpoint_kind is CompatEndpointKind.OPENAI:
            return [
                model.id
                for model in res.data
                if ("gpt" in model.id or "o3" in model.id.lower())
                and "audio" not in model.id.lower()
                and "realtime" not in model.id.lower()
            ]

        if endpoint_kind is CompatEndpointKind.OPENROUTER:
            return sorted(
                [model.id for model in res.data],
                key=lambda model_id: (
                    0
                    if any(
                        kw in model_id.lower() for kw in ["gpt", "gemini", "meta-llama"]
                    )
                    else 1,
                    model_id,
                ),
            )

        return [model.id for model in res.data]

    async def create_chat_step(
        self,
        model: str,
        messages: List[ChatCompletionMessageParam],
        kwargs: Dict[str, Any],
    ) -> ChatStepResult:
        response: ChatCompletion = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )

        choice = response.choices[0]
        message = choice.message
        tool_calls_raw = message.tool_calls
        tool_calls: List[ChatCompletionMessageToolCall] = (
            list(tool_calls_raw) if tool_calls_raw else []
        )
        assistant_extra_fields = self._get_assistant_extra_fields(message)
        return ChatStepResult(
            content=message.content,
            tool_calls=tool_calls,
            assistant_extra_fields=assistant_extra_fields,
            finish_reason=choice.finish_reason,
        )

    def _get_assistant_extra_fields(self, message: Any) -> Dict[str, Any]:
        extra_fields: Dict[str, Any] = {}
        for field_name in ASSISTANT_EXTRA_FIELD_NAMES:
            value = getattr(message, field_name, None)
            if value is not None:
                extra_fields[field_name] = value
        return extra_fields
