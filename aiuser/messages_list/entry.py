from dataclasses import dataclass
from typing import Literal, Union


@dataclass(frozen=True)
class MessageEntry:
    role: Literal['user', 'assistant', 'system']
    # content can be a string or a list of dicts
    content: Union[str, list[dict]]