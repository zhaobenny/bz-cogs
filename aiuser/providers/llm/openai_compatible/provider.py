from __future__ import annotations

import re
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

_OPENAI_EXCLUDED_TOKENS = frozenset(
    {
        "audio",
        "realtime",
        "live",
        "transcribe",
        "tts",
        "diarize",
        "image",
        "instruct",
        "moderation",
        "embedding",
        "whisper",
        "sora",
    }
)
_OPENAI_SPECIALIZED_TOKENS = frozenset(
    {"codex", "search", "research", "computer", "oss", "healthcare"}
)
_OPENAI_SPECIALIZED_FILLER_TOKENS = _OPENAI_SPECIALIZED_TOKENS | frozenset(
    {"api", "deep", "use"}
)
_OPENAI_O_SERIES_RE = re.compile(r"^o(\d+)(?:\.(\d+))?(?:[-_](.*))?$")
_OPENAI_GPT_SERIES_RE = re.compile(
    r"^(chat)?gpt[-_.]?(\d+)(?:\.(\d+))?(o)?(?:[-_](.*))?$"
)
_OPENAI_ISO_DATE_RE = re.compile(r"(?:^|[-_])(\d{4})[-_](\d{2})[-_](\d{2})(?=$|[-_])")
_OPENAI_LEGACY_DATE_RE = re.compile(
    r"(?:^|[-_])(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?=$|[-_])"
)
_OPENAI_SERIES_PRIORITY = {"gpt": 1, "o": 0, "other": -1}


def _openai_base_model_id(lowered: str) -> tuple[str, bool]:
    if not lowered.startswith("ft:"):
        return lowered, False
    parts = lowered.split(":", 2)
    base = parts[1] if len(parts) >= 2 else lowered[3:]
    return base, True


def _is_openai_chat_model(model_id: str) -> bool:
    lowered = model_id.strip().lower()
    if not lowered:
        return False
    base_id, _ = _openai_base_model_id(lowered)
    if "gpt" not in base_id and not _OPENAI_O_SERIES_RE.match(base_id):
        return False
    tokens = set(re.split(r"[-_:.]+", base_id))
    return not _OPENAI_EXCLUDED_TOKENS.intersection(tokens)


def _parse_openai_model(model_id: str, created: int) -> dict[str, Any]:
    lowered = model_id.strip().lower()
    base_id, is_finetune = _openai_base_model_id(lowered)

    is_snapshot = False
    snapshot_date = (0, 0, 0)
    unpinned_id = base_id

    iso_match = _OPENAI_ISO_DATE_RE.search(unpinned_id)
    if iso_match:
        is_snapshot = True
        snapshot_date = (
            int(iso_match.group(1)),
            int(iso_match.group(2)),
            int(iso_match.group(3)),
        )
        unpinned_id = (
            unpinned_id[: iso_match.start()] + unpinned_id[iso_match.end() :]
        ).strip("-_")
    else:
        legacy_match = _OPENAI_LEGACY_DATE_RE.search(unpinned_id)
        if legacy_match:
            is_snapshot = True
            unpinned_id = (
                unpinned_id[: legacy_match.start()] + unpinned_id[legacy_match.end() :]
            ).strip("-_")

    is_chatgpt = False
    gpt_match = _OPENAI_GPT_SERIES_RE.match(unpinned_id)
    o_match = _OPENAI_O_SERIES_RE.match(unpinned_id)
    if gpt_match:
        series = "gpt"
        is_chatgpt = bool(gpt_match.group(1))
        major = int(gpt_match.group(2))
        minor = int(gpt_match.group(3) or 0)
        is_o_suffix = bool(gpt_match.group(4))
        rest = gpt_match.group(5) or ""
        rest_tokens = [token for token in re.split(r"[-_]+", rest) if token]
        subgen = 2 if is_o_suffix else (1 if "turbo" in rest_tokens else 0)
        version = (major, minor, subgen)
        family_key: tuple[Any, ...] = (series, version)
    elif o_match:
        series = "o"
        major = int(o_match.group(1))
        minor = int(o_match.group(2) or 0)
        rest = o_match.group(3) or ""
        rest_tokens = [token for token in re.split(r"[-_]+", rest) if token]
        version = (major, minor, 0)
        family_key = (series, version)
    else:
        series = "other"
        rest_tokens = [token for token in re.split(r"[-_]+", unpinned_id) if token]
        version = (0, 0, 0)
        family_key = (series, unpinned_id)

    is_specialized = bool(_OPENAI_SPECIALIZED_TOKENS.intersection(rest_tokens))
    if is_finetune:
        tier = 3
    elif is_snapshot:
        tier = 2
    elif is_specialized:
        tier = 1
    else:
        tier = 0

    is_preview = 1 if "preview" in rest_tokens else 0
    modifier_tokens = [
        token
        for token in rest_tokens
        if token not in _OPENAI_SPECIALIZED_FILLER_TOKENS
        and token not in {"turbo", "preview"}
    ]
    if is_chatgpt or "chat" in modifier_tokens or "latest" in modifier_tokens:
        size_rank = 6
    elif not modifier_tokens:
        size_rank = 0
    elif "astra" in modifier_tokens:
        size_rank = 1
    elif "sol" in modifier_tokens:
        size_rank = 2
    elif "terra" in modifier_tokens:
        size_rank = 3
    elif "mini" in modifier_tokens or "luna" in modifier_tokens:
        size_rank = 4
    elif "nano" in modifier_tokens:
        size_rank = 5
    elif "pro" in modifier_tokens:
        size_rank = 7
    elif "max" in modifier_tokens:
        size_rank = 8
    else:
        size_rank = 9

    return {
        "id": model_id,
        "lowered": lowered,
        "created": created,
        "tier": tier,
        "is_specialized": is_specialized,
        "series": series,
        "version": version,
        "family_key": family_key,
        "is_preview": is_preview,
        "size_rank": size_rank,
        "snapshot_date": snapshot_date,
    }


def _sort_openai_models(raw_models: list[Any]) -> list[str]:
    deduped: dict[str, int] = {}
    for model in raw_models:
        model_id = getattr(model, "id", None)
        if not isinstance(model_id, str) or not _is_openai_chat_model(model_id):
            continue
        raw_created = getattr(model, "created", 0)
        created = (
            int(raw_created)
            if isinstance(raw_created, (int, float))
            and not isinstance(raw_created, bool)
            else 0
        )
        if model_id not in deduped or created > deduped[model_id]:
            deduped[model_id] = created

    parsed = [
        _parse_openai_model(model_id, created) for model_id, created in deduped.items()
    ]

    # Pick each family's representative creation timestamp from its highest-priority
    # canonical model (ignoring fine-tunes) so variants stay grouped together.
    family_best: dict[tuple[Any, ...], tuple[int, int, int, int]] = {}
    for entry in parsed:
        if entry["tier"] == 3:
            continue
        candidate = (
            entry["tier"],
            entry["is_preview"],
            entry["size_rank"],
            -entry["created"],
        )
        current = family_best.get(entry["family_key"])
        if current is None or candidate < current:
            family_best[entry["family_key"]] = candidate

    family_created: dict[tuple[Any, ...], int] = {
        family_key: -best[3] for family_key, best in family_best.items()
    }

    # Keep version ordering monotonic within each versioned series even if a newer
    # version was pre-registered slightly earlier in OpenAI's catalog.
    for series in ("gpt", "o"):
        series_families = sorted(
            (key for key in family_created if key[0] == series),
            key=lambda key: key[1],
        )
        running_max = 0
        for key in series_families:
            running_max = max(running_max, family_created[key])
            family_created[key] = running_max

    def sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
        tier = entry["tier"]
        if tier == 3:
            return (
                3,
                0,
                -entry["created"],
                0,
                (),
                0,
                0,
                (),
                -entry["created"],
                entry["lowered"],
            )
        return (
            tier,
            1 if (tier == 2 and entry["is_specialized"]) else 0,
            -family_created.get(entry["family_key"], entry["created"]),
            -_OPENAI_SERIES_PRIORITY[entry["series"]],
            tuple(-part for part in entry["version"]),
            entry["is_preview"],
            entry["size_rank"],
            tuple(-part for part in entry["snapshot_date"]),
            -entry["created"],
            entry["lowered"],
        )

    parsed.sort(key=sort_key)
    return [entry["id"] for entry in parsed]


async def list_openai_compat_models(
    openai_client: AsyncOpenAI, endpoint_url: str | None
) -> list[str]:
    endpoint_kind = get_openai_compat_kind(endpoint_url)
    if endpoint_kind is CompatEndpointKind.OPENROUTER:
        res = await openai_client.models.list(extra_query={"sort": "most-popular"})
    else:
        res = await openai_client.models.list()

    if endpoint_kind is CompatEndpointKind.OPENAI:
        return _sort_openai_models(list(res.data))

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
