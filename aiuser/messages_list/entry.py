from dataclasses import dataclass
from typing import Literal, Union


@dataclass(frozen=True)
class MessageEntry:
    role: Literal['user', 'assistant', 'system']
    content: Union[str, list]
