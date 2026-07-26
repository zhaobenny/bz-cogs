"""Retrieval of relevant memories using semantic similarity search."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from redbot.core import commands

from aiuser.config.defaults import DEFAULT_MEMORY_RETRIEVAL_PREFIX

if TYPE_CHECKING:
    from aiuser.providers.vectorstore import VectorStore

logger = logging.getLogger("red.bz_cogs.aiuser.memory")


async def fetch_relevant_memory(
    ctx: commands.Context, db: "VectorStore", query: str, threshold: float = 0.75
) -> Optional[str]:
    """Return the most relevant memory above the similarity threshold, prompt-formatted."""
    if not query.strip():
        return None

    try:
        memory_results = await db.search_similar(
            query,
            ctx.guild.id,
            k=1,
            user=str(ctx.author.id),
            channel=str(ctx.channel.id),
        )
    except Exception:
        logger.exception("Database error while searching memories")
        return None

    score = memory_results[0][2] if memory_results else 0

    logger.debug(
        f"Memory search score: {score:.3f} (threshold: {threshold}) for query: {query[:50]}..."
    )
    if score >= threshold:
        return f"{DEFAULT_MEMORY_RETRIEVAL_PREFIX} `{memory_results[0][1]}`"

    return None
