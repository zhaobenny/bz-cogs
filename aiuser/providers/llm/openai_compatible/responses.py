from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageToolCall
from redbot.core import Config

from aiuser.providers.llm.base import ChatStepResult, LLMProvider

logger = logging.getLogger("red.bz_cogs.aiuser.providers.llm")

RESPONSES_OUTPUT_FIELD = "_aiuser_responses_output"
_UNSUPPORTED_REQUEST_KEYS = (
    "logit_bias",
    "stop",
    "n",
    "frequency_penalty",
    "presence_penalty",
    "logprobs",
    "seed",
    "function_call",
    "functions",
)


def _message_content(content: Any) -> str | list[dict[str, Any]] | None:
    if isinstance(content, str):
        return content
    parts = []
    for item in content or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            parts.append({"type": "input_text", "text": item.get("text", "")})
        elif item.get("type") == "image_url":
            image = item.get("image_url") or {}
            if image.get("url"):
                part = {"type": "input_image", "image_url": image["url"]}
                if image.get("detail"):
                    part["detail"] = image["detail"]
                parts.append(part)
    if not parts:
        return None
    if len(parts) == 1 and parts[0]["type"] == "input_text":
        return parts[0]["text"]
    return parts


def _append_assistant_calls(
    items: list[dict[str, Any]], message: dict[str, Any]
) -> None:
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        if function.get("name"):
            items.append(
                {
                    "type": "function_call",
                    "call_id": call.get("id") or "call_unknown",
                    "name": function["name"],
                    "arguments": function.get("arguments") or "{}",
                }
            )


def build_responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "assistant" and message.get(RESPONSES_OUTPUT_FIELD):
            items.extend(message[RESPONSES_OUTPUT_FIELD])
            continue
        if role == "tool":
            if message.get("tool_call_id"):
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": str(message["tool_call_id"]),
                        "output": str(content or ""),
                    }
                )
            continue
        if role not in {"system", "user", "developer", "assistant"}:
            continue
        converted = _message_content(content)
        if converted is not None and converted != "":
            items.append({"type": "message", "role": role, "content": converted})
        if role == "assistant":
            _append_assistant_calls(items, message)
    return items


def build_responses_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        function = tool.get("function") or {}
        if not function.get("name"):
            continue
        converted.append(
            {
                "type": "function",
                "name": function["name"],
                "description": function.get("description", ""),
                "parameters": function.get("parameters", {"type": "object"}),
                "strict": function.get("strict", False),
            }
        )
    return converted


def _drop_unsupported_kwargs(request: dict[str, Any]) -> list[str]:
    dropped = [key for key in _UNSUPPORTED_REQUEST_KEYS if key in request]
    for key in dropped:
        request.pop(key)
    return dropped


def _request_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    request = dict(kwargs)
    extra_body = request.pop("extra_body", None)
    if isinstance(extra_body, dict):
        request.update(extra_body)
    reasoning_effort = request.pop("reasoning_effort", None)
    response_format = request.pop("response_format", None)
    provided_tools = request.pop("tools", None)
    dropped = _drop_unsupported_kwargs(request)
    for key in ("max_completion_tokens", "max_tokens"):
        value = request.pop(key, None)
        if value is not None:
            request.setdefault("max_output_tokens", value)
    if reasoning_effort is not None:
        request.setdefault("reasoning", {"effort": reasoning_effort})
    if response_format is not None:
        request["text"] = {
            **(request.get("text") or {}),
            "format": _response_format(response_format),
        }
    if provided_tools:
        request["tools"] = build_responses_tools(provided_tools)
    choice = request.get("tool_choice")
    if (
        isinstance(choice, dict)
        and choice.get("type") == "function"
        and "function" in choice
    ):
        function = choice["function"] or {}
        request["tool_choice"] = {"type": "function", "name": function.get("name")}
    if dropped:
        logger.warning("Ignoring unsupported Responses request kwargs: %s", dropped)
    request.pop("model", None)
    request.pop("input", None)
    return request


def _response_format(response_format: Any) -> Any:
    if not isinstance(response_format, dict):
        return response_format
    response_format = dict(response_format)
    schema = response_format.pop("json_schema", None)
    if isinstance(schema, dict):
        response_format.update(schema)
    return response_format


def _prepare_responses_request(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    request = _request_kwargs(kwargs)
    request.update(store=False, stream=False)
    include = list(request.get("include") or [])
    if "reasoning.encrypted_content" not in include:
        include.append("reasoning.encrypted_content")
    request["include"] = include
    if model.startswith("gpt-6-astra") or model == "gpt-astra-latest":
        _prepare_astra_request(request)
    return request


def _prepare_astra_request(request: dict[str, Any]) -> None:
    stripped = [
        key for key in ("temperature", "top_p", "top_logprobs") if key in request
    ]
    for key in stripped:
        request.pop(key)
    if stripped:
        logger.warning("Ignoring Astra-incompatible Responses kwargs: %s", stripped)
    request["include"] = [
        value for value in request["include"] if value != "message.output_text.logprobs"
    ]
    reasoning = request.get("reasoning")
    if isinstance(reasoning, dict) and reasoning.get("effort") in {"none", "minimal"}:
        request["reasoning"] = {**reasoning, "effort": "low"}


def _output_tool_call(item: dict[str, Any]) -> ChatCompletionMessageToolCall | None:
    if item.get("type") != "function_call" or not item.get("name"):
        return None
    return ChatCompletionMessageToolCall(
        id=item.get("call_id") or item.get("id") or "call_unknown",
        type="function",
        function={
            "name": item["name"],
            "arguments": item.get("arguments") or "{}",
        },
    )


def _output_text(item: dict[str, Any]) -> list[str]:
    if item.get("type") != "message":
        return []
    fields = {"output_text": "text", "refusal": "refusal"}
    chunks = []
    for part in item.get("content", []):
        field = fields.get(part.get("type"))
        if field and part.get(field):
            chunks.append(part[field])
    return chunks


def _parse_responses_output(response: Any) -> ChatStepResult:
    status = getattr(response, "status", None)
    output = [
        item.model_dump(mode="json", exclude_none=True) for item in response.output
    ]
    tool_calls: list[ChatCompletionMessageToolCall] = []
    text_chunks: list[str] = []
    for item in output:
        tool_call = _output_tool_call(item)
        if tool_call:
            tool_calls.append(tool_call)
        text_chunks.extend(_output_text(item))
    content = "\n".join(text_chunks).strip() or None
    if status == "incomplete":
        tool_calls = []
    if tool_calls:
        content = None
    return ChatStepResult(
        content=content,
        tool_calls=tool_calls,
        assistant_extra_fields={RESPONSES_OUTPUT_FIELD: output} if tool_calls else {},
        finish_reason=status,
    )


class OpenAIResponsesProvider(LLMProvider):
    def __init__(self, config: Config, openai_client: AsyncOpenAI):
        super().__init__(config)
        self.openai_client = openai_client

    async def list_models(self) -> list[str]:
        response = await self.openai_client.models.list()
        return [
            model.id
            for model in response.data
            if ("gpt" in model.id or "o3" in model.id.lower())
            and "audio" not in model.id.lower()
            and "realtime" not in model.id.lower()
        ]

    async def create_chat_step(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> ChatStepResult:
        input_items = build_responses_input(messages)
        request = _prepare_responses_request(model, kwargs)
        transport = {
            key: request.pop(key)
            for key in ("extra_headers", "extra_query", "timeout")
            if key in request
        }
        response = await self.openai_client.responses.create(
            model=model, input=input_items, extra_body=request, **transport
        )
        status = getattr(response, "status", None)
        if getattr(response, "error", None) is not None or status in {
            "failed",
            "cancelled",
        }:
            raise RuntimeError(
                f"Responses API request {status or 'failed'}: "
                f"{getattr(response, 'error', None)!r}"
            )
        if not response.output:
            raise RuntimeError("Responses API returned no output items")
        return _parse_responses_output(response)
