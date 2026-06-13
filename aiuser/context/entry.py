from dataclasses import dataclass, field
from typing import Literal, Optional, Union


@dataclass(frozen=True)
class MessageEntry:
    """One chat-completion message.

    ``name`` optionally tags special system messages (eg. ``"memory"``,
    ``"summary"``) so providers can distinguish them from the persona prompt
    without sniffing content strings.
    """

    role: Literal["user", "assistant", "system", "tool"]
    content: Union[str, list]
    tool_calls: list = field(default_factory=list)
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


SYSTEM_NAME_MEMORY = "memory"
SYSTEM_NAME_SUMMARY = "summary"
