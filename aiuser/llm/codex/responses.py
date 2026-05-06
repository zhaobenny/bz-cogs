import logging
from typing import Any, Dict, List, Optional

import httpx
from openai.types.chat import ChatCompletionMessageToolCall
from redbot.core import Config

from aiuser.config.defaults import DEFAULT_MEMORY_RETRIEVAL_PREFIX
from aiuser.llm.codex.oauth import CODEX_RESPONSES_URL, ensure_valid_codex_oauth

logger = logging.getLogger("red.bz_cogs.aiuser.llm")

CODEX_CONTEXT_PREFIX = "Additional system context:\n"


def _parse_data_uri(url: str) -> Dict[str, str]:
    header, data = url.split(",", 1)
    media_type = header[5:].split(";", 1)[0]
    return {"type": "base64", "media_type": media_type, "data": data}


def _convert_content_parts(content: Any) -> List[Dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]

    parts = []
    for item in content or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            parts.append({"type": "input_text", "text": item.get("text", "")})
            continue
        if item.get("type") != "image_url":
            continue

        image_url = ((item.get("image_url") or {}).get("url") or "").strip()
        if not image_url:
            continue

        if image_url.startswith("data:"):
            parts.append(
                {
                    "type": "input_image",
                    "source": _parse_data_uri(image_url),
                }
            )
        else:
            parts.append(
                {
                    "type": "input_image",
                    "source": {"type": "url", "url": image_url},
                }
            )
    return parts


def _convert_message_content(content: Any) -> Any:
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None

    parts = _convert_content_parts(content)
    if not parts:
        return None

    if len(parts) == 1 and parts[0].get("type") == "input_text":
        return parts[0].get("text", "")

    return parts


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    chunks: List[str] = []
    for item in content or []:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())

    return "\n".join(chunks).strip()


def _first_system_message_index(messages: List[Dict[str, Any]]) -> Optional[int]:
    fallback_index: Optional[int] = None
    for index, message in enumerate(messages):
        if message.get("role") != "system":
            continue
        if fallback_index is None:
            fallback_index = index
        if _stringify_content(message.get("content")).startswith(
            DEFAULT_MEMORY_RETRIEVAL_PREFIX
        ):
            continue
        return index
    return fallback_index


def _tool_call_id(tool_call: Any, fallback: int) -> str:
    return getattr(tool_call, "id", None) or tool_call.get("id") or f"call_{fallback}"


def _tool_function(tool_call: Any) -> Any:
    return getattr(tool_call, "function", None) or tool_call.get("function") or {}


def build_codex_instructions(
    messages: List[Dict[str, Any]], kwargs: Dict[str, Any]
) -> str:
    sections: List[str] = []
    first_system_index = _first_system_message_index(messages)

    instructions = kwargs.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        sections.append(instructions.strip())

    extra_body = kwargs.get("extra_body")
    if isinstance(extra_body, dict):
        extra_instructions = extra_body.get("instructions")
        if isinstance(extra_instructions, str) and extra_instructions.strip():
            sections.append(extra_instructions.strip())

    for index, message in enumerate(messages):
        role = message.get("role")
        if role == "developer" or index == first_system_index:
            content = _stringify_content(message.get("content"))
            if content:
                sections.append(content)

    return "\n\n".join(sections).strip()


def build_codex_input(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    first_system_index = _first_system_message_index(messages)
    for index, message in enumerate(messages):
        role = message.get("role")
        content = message.get("content")
        tool_calls = message.get("tool_calls") or []

        if role == "tool":
            tool_call_id = message.get("tool_call_id")
            if tool_call_id:
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": str(tool_call_id),
                        "output": str(content or ""),
                    }
                )
            continue

        if role == "system":
            if index == first_system_index:
                continue
            text = _stringify_content(content)
            if text:
                items.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": f"{CODEX_CONTEXT_PREFIX}{text}",
                    }
                )
            continue

        if role == "developer":
            continue

        message_content = _convert_message_content(content)
        if role in {"user", "assistant"} and message_content:
            items.append({"type": "message", "role": role, "content": message_content})

        if role != "assistant":
            continue

        for offset, tool_call in enumerate(tool_calls):
            function = _tool_function(tool_call)
            name = getattr(function, "name", None) or function.get("name")
            arguments = getattr(function, "arguments", None) or function.get(
                "arguments", "{}"
            )
            if not name:
                continue
            items.append(
                {
                    "type": "function_call",
                    "call_id": _tool_call_id(tool_call, index + offset),
                    "name": name,
                    "arguments": arguments,
                }
            )
    return items


def build_codex_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            }
        )
    return converted


def build_codex_payload(
    model: str, messages: List[Dict[str, Any]], kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    instructions = build_codex_instructions(messages, kwargs)
    extra_body = (
        kwargs.get("extra_body") if isinstance(kwargs.get("extra_body"), dict) else {}
    )
    payload: Dict[str, Any] = {
        "model": model,
        "instructions": instructions,
        "input": build_codex_input(messages),
        "store": False,
        "stream": True,
    }

    if kwargs.get("tools"):
        payload["tools"] = build_codex_tools(kwargs["tools"])

    if "max_output_tokens" in kwargs:
        payload["max_output_tokens"] = kwargs["max_output_tokens"]
    elif "max_tokens" in kwargs:
        payload["max_output_tokens"] = kwargs["max_tokens"]

    for key in ("temperature", "top_p", "reasoning"):
        if key in kwargs:
            payload[key] = kwargs[key]

    if extra_body.get("store") is False:
        payload["store"] = False

    unsupported_keys = sorted(
        key
        for key in kwargs
        if key
        not in {
            "extra_body",
            "instructions",
            "tools",
            "max_output_tokens",
            "max_tokens",
            "temperature",
            "top_p",
            "reasoning",
        }
    )
    if unsupported_keys:
        logger.debug("Ignoring unsupported Codex request kwargs: %s", unsupported_keys)

    return payload


def parse_codex_response(
    data: Dict[str, Any],
) -> tuple[Optional[str], List[ChatCompletionMessageToolCall]]:
    text_chunks: List[str] = []
    tool_calls: List[ChatCompletionMessageToolCall] = []

    for item in data.get("output", []):
        item_type = item.get("type")
        if item_type == "message" and item.get("role") == "assistant":
            for part in item.get("content", []):
                if part.get("type") == "output_text" and part.get("text"):
                    text_chunks.append(part["text"])
            continue

        if item_type != "function_call" or not item.get("name"):
            continue

        tool_calls.append(
            ChatCompletionMessageToolCall(
                id=item.get("call_id") or item.get("id") or "call_unknown",
                type="function",
                function={
                    "name": item["name"],
                    "arguments": item.get("arguments") or "{}",
                },
            )
        )

    if not text_chunks and data.get("output_text"):
        text_chunks.append(data["output_text"])

    content = "\n".join(chunk for chunk in text_chunks if chunk).strip() or None
    if content is None and not tool_calls:
        output_types = [
            item.get("type")
            for item in data.get("output", [])
            if isinstance(item, dict)
        ]
        logger.warning(
            "Codex response completed without content or function calls "
            "(id=%s status=%s output_types=%s incomplete_details=%s)",
            data.get("id"),
            data.get("status"),
            output_types,
            data.get("incomplete_details"),
        )
    return content, tool_calls


async def parse_codex_stream_response(
    response: httpx.Response,
) -> tuple[Optional[str], List[ChatCompletionMessageToolCall]]:
    event_name: Optional[str] = None
    data_lines: List[str] = []
    completed_payload: Optional[Dict[str, Any]] = None
    output_items: Dict[int, Dict[str, Any]] = {}
    output_text: Dict[int, str] = {}

    async for line in response.aiter_lines():
        if not line:
            if event_name and data_lines:
                payload_text = "\n".join(data_lines).strip()
                decoded = None
                if payload_text and payload_text != "[DONE]":
                    try:
                        decoded = httpx.Response(200, text=payload_text).json()
                    except ValueError:
                        pass

                if isinstance(decoded, dict):
                    if event_name == "response.output_item.done":
                        item = decoded.get("item")
                        output_index = decoded.get("output_index")
                        if isinstance(item, dict) and isinstance(output_index, int):
                            output_items[output_index] = item
                    elif event_name == "response.output_text.done":
                        output_index = decoded.get("output_index")
                        text = decoded.get("text")
                        if isinstance(output_index, int) and isinstance(text, str):
                            output_text[output_index] = text
                    elif event_name == "response.completed":
                        completed_payload = decoded.get("response") or decoded
                        break
            event_name = None
            data_lines = []
            continue

        if line.startswith("event: "):
            event_name = line[7:].strip()
            continue

        if line.startswith("data: "):
            data_lines.append(line[6:])

    if completed_payload is None:
        raise ValueError("Codex stream ended without response.completed payload")

    if not completed_payload.get("output"):
        output = [
            item
            for _, item in sorted(output_items.items(), key=lambda pair: pair[0])
            if isinstance(item, dict)
        ]
        for output_index, text in output_text.items():
            if any(index == output_index for index in output_items):
                continue
            output.append(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                }
            )
        if output:
            completed_payload = {**completed_payload, "output": output}

    return parse_codex_response(completed_payload)


async def create_codex_response(
    config: Config,
    model: str,
    messages: List[Dict[str, Any]],
    kwargs: Dict[str, Any],
) -> tuple[Optional[str], List[ChatCompletionMessageToolCall]]:
    timeout = await config.openai_endpoint_request_timeout()
    async with httpx.AsyncClient(timeout=timeout) as client:
        oauth = await ensure_valid_codex_oauth(config, client=client)
        payload = build_codex_payload(model, messages, kwargs)

        for attempt in range(2):
            headers = {"Authorization": f"Bearer {oauth['access']}"}
            if oauth.get("account_id"):
                headers["ChatGPT-Account-Id"] = oauth["account_id"]

            async with client.stream(
                "POST",
                CODEX_RESPONSES_URL,
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code == 401 and attempt == 0:
                    logger.warning("Codex request unauthorized, forcing token refresh")
                    await response.aread()
                    oauth = await ensure_valid_codex_oauth(
                        config, force_refresh=True, client=client
                    )
                    continue

                if not response.is_success:
                    body = (await response.aread()).decode(errors="replace")
                    logger.error(
                        "Codex request failed with status %s: %s",
                        response.status_code,
                        body[:500],
                    )
                    response.raise_for_status()

                return await parse_codex_stream_response(response)

    return None, []
