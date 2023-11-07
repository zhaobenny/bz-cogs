# enums.py

from enum import Enum


class ScanImageMode(Enum):
    LOCAL = "local"
    AI_HORDE = "ai-horde"
    GPT4  = "gpt-4-vision-preview"