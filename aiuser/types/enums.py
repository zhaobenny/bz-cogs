from enum import Enum, auto


class MentionType(Enum):
    SERVER = auto()
    USER = auto()
    ROLE = auto()
    CHANNEL = auto()
