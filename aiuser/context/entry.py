from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class MessageEntry:
    """Single chat-completion message."""

    role: Literal["user", "assistant", "system", "tool"]
    content: str | list
    tool_calls: list = field(default_factory=list)
    tool_call_id: str | None = None
    assistant_extra_fields: dict[str, Any] = field(default_factory=dict)
