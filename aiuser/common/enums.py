# enums.py

from enum import Enum


class ScanImageMode(Enum):
    LOCAL = "local"
    AI_HORDE = "ai-horde"
    LLM = "supported-llm"
