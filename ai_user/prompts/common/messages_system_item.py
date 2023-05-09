from dataclasses import dataclass

@dataclass(frozen=True)
class MessagesSystemItem:
    content: str
    role : str = "system"
