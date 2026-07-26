from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, Union


@dataclass(frozen=True)
class MessageEntry:
    """Single chat-completion message."""

    role: Literal["user", "assistant", "system", "tool"]
    content: Union[str, list]
    tool_calls: list = field(default_factory=list)
    tool_call_id: Optional[str] = None
    assistant_extra_fields: Dict[str, Any] = field(default_factory=dict)
