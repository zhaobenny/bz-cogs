from enum import Enum, auto


class ScanImageMode(Enum):
    LOCAL = "local"
    AI_HORDE = "ai-horde"
    LLM = "supported-llm"

class MentionType(Enum):
    SERVER = auto()
    USER = auto()
    ROLE = auto()
    CHANNEL = auto()
