from __future__ import annotations

from typing import Any, ClassVar

import httpx

from aiuser.config.constants import DECISION_REQUEST_TIMEOUT
from aiuser.providers.decision.base import (
    DecisionProvider,
    DecisionResult,
    PredicateQuestion,
)


def _serialize_predicate(question: PredicateQuestion) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "noul",
        "instructions": question.instructions,
    }
    criteria: dict[str, str] = {}
    if question.true_criteria:
        criteria["true"] = question.true_criteria
    if question.false_criteria:
        criteria["false"] = question.false_criteria
    if criteria:
        payload["criteria"] = criteria
    return payload


def _parse_probabilities(raw_answers: Any) -> dict[str, float]:
    probabilities: dict[str, float] = {}
    if not isinstance(raw_answers, dict):
        return probabilities
    for name, item in raw_answers.items():
        if not isinstance(item, dict):
            continue
        prob = item.get("noul")
        if prob is None:
            prob = item.get("probability")
        if prob is not None:
            probabilities[str(name)] = float(prob)
    return probabilities


class NoulDecisionProvider(DecisionProvider):
    """Shared base for Noul/TypeSafe Decisions API backends."""

    default_endpoint: str
    extra_headers: ClassVar[dict[str, str]] = {}

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str | None = None,
        timeout: float = DECISION_REQUEST_TIMEOUT,
    ):
        self.api_key = api_key
        self.endpoint = endpoint or self.default_endpoint
        self.timeout = timeout

    async def evaluate(
        self,
        *,
        model: str,
        state: dict[str, Any] | str,
        questions: list[PredicateQuestion],
    ) -> DecisionResult:
        body = {
            "model": model,
            "state": state,
            "questions": {q.name: _serialize_predicate(q) for q in questions},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.endpoint, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

        return DecisionResult(
            probabilities=_parse_probabilities(data.get("answers")),
            model=data.get("model") or model,
            provider=self.name,
        )
