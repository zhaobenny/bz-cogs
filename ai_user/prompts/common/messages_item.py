from dataclasses import dataclass

from ai_user.prompts.common.helpers import RoleType

@dataclass(frozen=True)
class MessagesItem:
    role: RoleType
    content: str
