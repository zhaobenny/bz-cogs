from dataclasses import dataclass

from ai_user.common.types import RoleType


@dataclass(frozen=True)
class MessagesItem:
    role: RoleType
    content: str
