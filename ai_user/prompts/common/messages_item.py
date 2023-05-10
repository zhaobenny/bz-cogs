from dataclasses import dataclass
from typing import Literal

RoleType = Literal['user', 'assistant', 'system']

@dataclass(frozen=True)
class MessagesItem:
    role: RoleType
    content: str
