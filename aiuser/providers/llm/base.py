from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from openai.types.chat import ChatCompletionMessageParam, ChatCompletionMessageToolCall
from redbot.core import Config


@dataclass
class ChatStepResult:
    content: str | None
    tool_calls: list[ChatCompletionMessageToolCall]
    assistant_extra_fields: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None


class LLMProvider(ABC):
    def __init__(self, config: Config):
        self.config = config

    @abstractmethod
    async def list_models(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def create_chat_step(
        self,
        model: str,
        messages: list[ChatCompletionMessageParam],
        kwargs: dict[str, Any],
    ) -> ChatStepResult:
        raise NotImplementedError
