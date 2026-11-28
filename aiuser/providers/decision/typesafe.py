from __future__ import annotations

from aiuser.config.constants import (
    DEFAULT_TYPESAFE_DECISION_MODEL,
    TYPESAFE_DECISIONS_URL,
)
from aiuser.providers.decision.noul import NoulDecisionProvider


class TypeSafeDecisionProvider(NoulDecisionProvider):
    """Direct TypeSafe System One API (`POST https://api.typesafe.ai/v1/systemone`)."""

    name = "typesafe"
    default_model = DEFAULT_TYPESAFE_DECISION_MODEL
    default_endpoint = TYPESAFE_DECISIONS_URL
