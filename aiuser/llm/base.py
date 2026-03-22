from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageParam, ChatCompletionMessageToolCall
from redbot.core import Config


@dataclass
class ChatStepResult:
    content: Optional[str]
    tool_calls: List[ChatCompletionMessageToolCall]


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
        messages: List[ChatCompletionMessageParam],
        kwargs: Dict[str, Any],
    ) -> ChatStepResult:
        raise NotImplementedError
