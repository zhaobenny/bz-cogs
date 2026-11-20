from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCall,
)
from redbot.core import Config

from aiuser.providers.llm.base import ChatStepResult, LLMProvider
from aiuser.providers.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_kind,
)

ASSISTANT_EXTRA_FIELD_NAMES = ("reasoning", "reasoning_details")


async def list_openai_compat_models(
    openai_client: AsyncOpenAI, endpoint_url: str | None
) -> list[str]:
    endpoint_kind = get_openai_compat_kind(endpoint_url)
    if endpoint_kind is CompatEndpointKind.OPENROUTER:
        res = await openai_client.models.list(extra_query={"sort": "most-popular"})
    else:
        res = await openai_client.models.list()

    if endpoint_kind is CompatEndpointKind.OPENAI:
        return [
            model.id
            for model in res.data
            if isinstance(model.id, str)
            and ("gpt" in model.id or "o3" in model.id.lower())
            and "audio" not in model.id.lower()
            and "realtime" not in model.id.lower()
        ]

    if endpoint_kind is CompatEndpointKind.OPENROUTER:
        models = []
        for model in res.data:
            if not isinstance(model.id, str):
                continue
            model_id = model.id.lower()
            if ":batch" in model_id:
                continue
            arch = getattr(model, "architecture", None)
            output_modalities = (
                arch.get("output_modalities") if isinstance(arch, dict) else None
            )
            if isinstance(output_modalities, list) and output_modalities:
                if "text" not in output_modalities:
                    continue
                if any(
                    mod in model_id and mod in output_modalities
                    for mod in ("image", "audio", "video")
                ):
                    continue
            models.append(model.id)
        featured = []
        for prefix in ("openai/gpt", "anthropic/claude", "google/gemini"):
            family = list(
                dict.fromkeys(
                    model for model in models if model.lower().startswith(prefix)
                )
            )
            featured.extend(family[:3])
        featured.extend(model for model in models if model not in featured)
        return featured

    return [model.id for model in res.data if isinstance(model.id, str)]


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, config: Config, openai_client: AsyncOpenAI):
        super().__init__(config)
        self.openai_client = openai_client

    async def list_models(self) -> list[str]:
        return await list_openai_compat_models(
            self.openai_client, await self.config.custom_openai_endpoint()
        )

    async def create_chat_step(
        self,
        model: str,
        messages: list[ChatCompletionMessageParam],
        kwargs: dict[str, Any],
    ) -> ChatStepResult:
        request_kwargs = dict(kwargs)
        endpoint_kind = get_openai_compat_kind(
            await self.config.custom_openai_endpoint()
        )
        native_tools = request_kwargs.pop("native_tools", [])
        if endpoint_kind is CompatEndpointKind.OPENROUTER:
            tools = list(request_kwargs.get("tools", []))
            if "web_search" in native_tools:
                tools.append(
                    {
                        "type": "openrouter:web_search",
                        "parameters": {"engine": "auto"},
                    }
                )
            if "fetch_url" in native_tools:
                tools.append(
                    {"type": "openrouter:web_fetch", "parameters": {"engine": "auto"}}
                )
            if tools:
                request_kwargs["tools"] = tools
        response: ChatCompletion = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            **request_kwargs,
        )

        choices = response.choices or []
        if not choices:
            response_error = getattr(response, "error", None)
            if response_error is None:
                response_error = (getattr(response, "model_extra", None) or {}).get(
                    "error"
                )
            raise RuntimeError(
                "LLM response contained no choices"
                + (f": {response_error!r}" if response_error is not None else "")
            )

        choice = choices[0]
        if endpoint_kind is CompatEndpointKind.OPENROUTER:
            choice_error = getattr(choice, "error", None)
            if choice_error is not None:
                raise RuntimeError(
                    f"OpenRouter provider returned an error: {choice_error!r}"
                )

        message = choice.message
        tool_calls_raw = message.tool_calls
        tool_calls: list[ChatCompletionMessageToolCall] = (
            list(tool_calls_raw) if tool_calls_raw else []
        )
        assistant_extra_fields = self._get_assistant_extra_fields(message)
        return ChatStepResult(
            content=message.content,
            tool_calls=tool_calls,
            assistant_extra_fields=assistant_extra_fields,
            finish_reason=choice.finish_reason,
        )

    def _get_assistant_extra_fields(
        self, message: ChatCompletionMessage
    ) -> dict[str, Any]:
        extra_fields: dict[str, Any] = {}
        for field_name in ASSISTANT_EXTRA_FIELD_NAMES:
            value = getattr(message, field_name, None)
            if value is not None:
                extra_fields[field_name] = value
        return extra_fields
