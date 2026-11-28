from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PredicateQuestion:
    """Boolean (predicate/noul) question returning a calibrated probability in [0, 1]."""

    name: str
    instructions: str
    true_criteria: str | None = None
    false_criteria: str | None = None


@dataclass(frozen=True)
class DecisionResult:
    probabilities: dict[str, float]
    model: str | None = None
    provider: str | None = None


class DecisionProvider(ABC):
    """Backend adapter for System One / Decisions API models."""

    name: str
    default_model: str

    @abstractmethod
    async def evaluate(
        self,
        *,
        model: str,
        state: dict[str, Any] | str,
        questions: list[PredicateQuestion],
    ) -> DecisionResult:
        raise NotImplementedError
