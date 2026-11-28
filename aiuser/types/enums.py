from __future__ import annotations

from enum import Enum, auto


class MentionType(Enum):
    SERVER = auto()
    USER = auto()
    ROLE = auto()
    CHANNEL = auto()


class ReplyMode(str, Enum):
    CHANCE = "chance"
    DECISION = "decision"

    @classmethod
    def from_raw(cls, raw: str | None) -> ReplyMode:
        if raw is None:
            return cls.CHANCE
        try:
            return cls(raw)
        except ValueError:
            return cls.CHANCE
