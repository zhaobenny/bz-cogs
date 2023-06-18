from dataclasses import dataclass

from aiuser.common.types import RoleType


@dataclass(frozen=True)
class MessagesItem:
    role: RoleType
    content: str
