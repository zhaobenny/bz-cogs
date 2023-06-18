from dataclasses import dataclass

from aiuser.common.types import RoleType


@dataclass(frozen=True)
class MessageEntry:
    role: RoleType
    content: str
