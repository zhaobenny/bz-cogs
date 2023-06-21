from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class MessageEntry:
    role: Literal['user', 'assistant', 'system']
    content: str
