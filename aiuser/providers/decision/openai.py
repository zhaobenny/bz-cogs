from __future__ import annotations

import json
from typing import Any

import httpx

from aiuser.config.constants import (
    DECISION_REQUEST_TIMEOUT,
    DEFAULT_OPENAI_DECISION_MODEL,
    OPENAI_DECISIONS_URL,
)
from aiuser.providers.decision.base import (
    DecisionProvider,
    DecisionResult,
    PredicateQuestion,
)


def _serialize_predicate(question: PredicateQuestion) -> dict[str, Any]:
    instructions = question.instructions
    if question.true_criteria or question.false_criteria:
        parts = [instructions]
        if question.true_criteria:
            parts.append(f"True when: {question.true_criteria}")
        if question.false_criteria:
            parts.append(f"False when: {question.false_criteria}")
        instructions = "\n".join(parts)
    return {
        "type": "predicate",
        "name": question.name,
        "instructions": instructions,
    }


def _parse_probabilities(raw_answers: Any) -> dict[str, float]:
    probabilities: dict[str, float] = {}
    if not isinstance(raw_answers, list):
        return probabilities
    for item in raw_answers:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        prob = item.get("probability")
        if name and prob is not None:
            probabilities[str(name)] = float(prob)
    return probabilities


class OpenAIDecisionProvider(DecisionProvider):
    """OpenAI Decisions API (`POST /v1/decisions`)."""

    name = "openai"
    default_model = DEFAULT_OPENAI_DECISION_MODEL

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = OPENAI_DECISIONS_URL,
        timeout: float = DECISION_REQUEST_TIMEOUT,
    ):
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout

    async def evaluate(
        self,
        *,
        model: str,
        state: dict[str, Any] | str,
        questions: list[PredicateQuestion],
    ) -> DecisionResult:
        input_payload = (
            state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)
        )
        body = {
            "model": model,
            "input": input_payload,
            "questions": [_serialize_predicate(q) for q in questions],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
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
