"""Model-based reply decision policy powered by System One / Decisions APIs."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx
from redbot.core import commands

from aiuser.context.decision_state import build_decision_state
from aiuser.providers.decision import (
    DecisionResult,
    PredicateQuestion,
    resolve_decision_provider,
)

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser.decision")

QUESTION_DIRECTLY_NEEDED = "directly_needed"
QUESTION_GOOD_TIMING = "good_timing"
QUESTION_SHOULD_CONTRIBUTE = "should_contribute"


@dataclass(frozen=True)
class ReplyDecisionPolicy:
    """Calibrated probability thresholds for the 3-question reply rubric."""

    direct_threshold: float = 0.70
    direct_timing_floor: float = 0.35
    direct_contribute_floor: float = 0.15
    timing_threshold: float = 0.50
    contribute_threshold: float = 0.65


DEFAULT_REPLY_DECISION_POLICY = ReplyDecisionPolicy()


@dataclass(frozen=True)
class DecisionOutcome:
    should_reply: bool
    reason: str
    scores: dict[str, float] = field(default_factory=dict)
    model: str | None = None
    provider: str | None = None


def build_reply_questions(self_name: str) -> list[PredicateQuestion]:
    """Construct the orthogonal 3-question rubric evaluated in one decision call."""
    return [
        PredicateQuestion(
            name=QUESTION_DIRECTLY_NEEDED,
            instructions=(
                f"Does the latest message expect a direct reply from {self_name}?"
            ),
            true_criteria=(
                f"Someone is addressing {self_name}, continuing an active exchange "
                f"with {self_name}, or asking something {self_name}'s persona is "
                "specifically expected to answer."
            ),
            false_criteria=(
                f"The message is not directed at {self_name} or its role in "
                "self_persona, is aimed at another role or people who can take "
                f"an action {self_name} cannot, or is a brief closing "
                "acknowledgement that needs no further reply."
            ),
        ),
        PredicateQuestion(
            name=QUESTION_GOOD_TIMING,
            instructions=(
                f"Is right now a natural moment for {self_name} to reply in this channel?"
            ),
            true_criteria=(
                "The latest thought appears complete and replying now would feel "
                f"natural for {self_name}'s persona."
            ),
            false_criteria=(
                "Someone appears mid-thought, or replying right now would awkwardly "
                "interrupt an ongoing exchange."
            ),
        ),
        PredicateQuestion(
            name=QUESTION_SHOULD_CONTRIBUTE,
            instructions=(
                f"Based on {self_name}'s persona (self_persona), would replying "
                "here genuinely add something worthwhile?"
            ),
            true_criteria=(
                f"The message gives {self_name} a genuine opening to contribute "
                "something that fits self_persona's role, tone, or interests."
            ),
            false_criteria=(
                "The message falls outside self_persona's scope or interests, is "
                "low-signal noise, is meant for another role or people who can "
                f"take an action {self_name} cannot, or replying would feel forced "
                "or out of character."
            ),
        ),
    ]


def evaluate_policy(
    result: DecisionResult,
    policy: ReplyDecisionPolicy = DEFAULT_REPLY_DECISION_POLICY,
) -> DecisionOutcome:
    """Turn calibrated question probabilities into a single reply/ignore decision."""
    required = (
        QUESTION_DIRECTLY_NEEDED,
        QUESTION_GOOD_TIMING,
        QUESTION_SHOULD_CONTRIBUTE,
    )
    scores: dict[str, float] = {}

    def outcome(should_reply: bool, reason: str) -> DecisionOutcome:
        return DecisionOutcome(
            should_reply=should_reply,
            reason=reason,
            scores=scores,
            model=result.model,
            provider=result.provider,
        )

    for key in required:
        value = result.probabilities.get(key)
        if value is None or not math.isfinite(value) or not (0.0 <= value <= 1.0):
            return outcome(False, "incomplete_scores")
        scores[key] = value

    p_direct = scores[QUESTION_DIRECTLY_NEEDED]
    p_timing = scores[QUESTION_GOOD_TIMING]
    p_contribute = scores[QUESTION_SHOULD_CONTRIBUTE]

    if (
        p_direct >= policy.direct_threshold
        and p_timing >= policy.direct_timing_floor
        and p_contribute >= policy.direct_contribute_floor
    ):
        return outcome(True, "directly_needed")

    if p_timing < policy.timing_threshold:
        return outcome(False, "bad_timing")

    if p_contribute >= policy.contribute_threshold:
        return outcome(True, "should_contribute")

    return outcome(False, "low_relevance")


async def should_reply_with_decision_model(
    services: AIUserServices,
    ctx: commands.Context,
    *,
    seconds_since_bot_reply: float | None = None,
    policy: ReplyDecisionPolicy = DEFAULT_REPLY_DECISION_POLICY,
) -> DecisionOutcome:
    """Evaluate recent channel state via the configured decision model.

    Always fails closed (``should_reply=False``) when no backend is configured or
    on network/provider errors so outages never cause spam.
    """
    resolved = await resolve_decision_provider(services)
    if resolved is None:
        logger.warning(
            "Decision mode is enabled in guild %s, but no decision provider/key is available",
            ctx.guild.id,
        )
        return DecisionOutcome(should_reply=False, reason="no_provider")

    provider, model = resolved

    def reject(reason: str) -> DecisionOutcome:
        return DecisionOutcome(
            should_reply=False,
            reason=reason,
            model=model,
            provider=provider.name,
        )

    state = await build_decision_state(
        services,
        ctx,
        seconds_since_bot_reply=seconds_since_bot_reply,
    )
    if not state.get("recent_messages"):
        return reject("empty_context")

    questions = build_reply_questions(state["self_name"])
    try:
        result = await provider.evaluate(model=model, state=state, questions=questions)
    except httpx.TimeoutException:
        logger.warning("Decision model request timed out (%s/%s)", provider.name, model)
        return reject("timeout")
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Decision model request failed (%s/%s, status=%s)",
            provider.name,
            model,
            exc.response.status_code,
        )
        return reject("http_error")
    except Exception:
        logger.exception(
            "Unexpected error calling decision model (%s/%s)", provider.name, model
        )
        return reject("error")

    outcome = evaluate_policy(result, policy)
    logger.debug(
        "Decision (%s/%s): reply=%s [%s] direct=%.2f timing=%.2f contrib=%.2f",
        outcome.provider,
        outcome.model,
        outcome.should_reply,
        outcome.reason,
        outcome.scores.get(QUESTION_DIRECTLY_NEEDED, 0.0),
        outcome.scores.get(QUESTION_GOOD_TIMING, 0.0),
        outcome.scores.get(QUESTION_SHOULD_CONTRIBUTE, 0.0),
    )
    return outcome
