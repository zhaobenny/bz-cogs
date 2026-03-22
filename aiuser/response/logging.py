import json
import logging
from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageToolCall

logger = logging.getLogger("red.bz_cogs.aiuser")

_DEBUG_RESPONSE_PREVIEW_LIMIT = 200
_DEBUG_IMAGE_DATA_PREVIEW_LIMIT = 20
_DATA_URI_BASE64_MARKER = ";base64,"


def _to_debug_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _to_debug_value(value.model_dump(mode="json"))

    if isinstance(value, dict):
        return {key: _to_debug_value(inner) for key, inner in value.items()}

    if isinstance(value, (list, tuple)):
        return [_to_debug_value(inner) for inner in value]

    return value


def _truncate_data_uri(url: str) -> str:
    base64_start = url.find(_DATA_URI_BASE64_MARKER)
    if base64_start == -1:
        return url

    base64_start += len(_DATA_URI_BASE64_MARKER)
    preview = url[base64_start : base64_start + _DEBUG_IMAGE_DATA_PREVIEW_LIMIT]
    return f"{url[:base64_start]}{preview}..."


def _sanitize_content_item(item: Any) -> None:
    if not isinstance(item, dict):
        return
    if item.get("type") != "image_url":
        return

    image_url = item.get("image_url")
    if not isinstance(image_url, dict):
        return

    url = image_url.get("url")
    if isinstance(url, str) and url.startswith("data:"):
        image_url["url"] = _truncate_data_uri(url)


def _sanitize_message(message: Any) -> None:
    if not isinstance(message, dict):
        return

    content = message.get("content")
    if not isinstance(content, list):
        return

    for item in content:
        _sanitize_content_item(item)


def sanitize_messages_for_debug(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sanitized_messages = _to_debug_value(messages)

    for message in sanitized_messages:
        _sanitize_message(message)

    return sanitized_messages


def _format_response_preview(content: str) -> str:
    preview = content[:_DEBUG_RESPONSE_PREVIEW_LIMIT].strip().replace("\n", " ")
    if len(content) > _DEBUG_RESPONSE_PREVIEW_LIMIT:
        return f"{preview}..."
    return preview


def _get_tool_call_names(
    tool_calls: List[ChatCompletionMessageToolCall],
) -> List[Optional[str]]:
    return [tool_call.function.name for tool_call in tool_calls]


def log_chat_request(messages: List[Dict[str, Any]]) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return

    try:
        sanitized_messages = sanitize_messages_for_debug(messages)
        logger.debug(
            "Sending LLM prompt:\n%s", json.dumps(sanitized_messages, indent=4)
        )
    except Exception as exc:
        logger.debug("Error logging LLM prompt: %s", exc)


def log_chat_step_result(
    content: Optional[str],
    tool_calls: List[ChatCompletionMessageToolCall],
) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return

    if content:
        logger.debug(
            'Generated response: "%s"',
            _format_response_preview(content),
        )

    if tool_calls:
        logger.debug(
            "Received tool calls: %s",
            _get_tool_call_names(tool_calls),
        )
