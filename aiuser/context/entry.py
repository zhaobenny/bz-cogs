from dataclasses import dataclass, field
from typing import Literal, Union


@dataclass(frozen=True)
class MessageEntry:
    role: Literal['user', 'assistant', 'system', 'tool']
    content: Union[str, list]
    tool_calls: list = field(default_factory=list)
    tool_call_id: int = None
