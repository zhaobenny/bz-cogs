
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Parameters:
    properties: dict
    required: list = field(default_factory=list)
    type: str = "object"


@dataclass(frozen=True)
class Function:
    name: str
    description: str
    parameters: Parameters


@dataclass(frozen=True)
class ToolCallSchema:
    function: Function
    type: str = "function"

    def __hash__(self):
        return hash(self.function.name + self.function.description)
