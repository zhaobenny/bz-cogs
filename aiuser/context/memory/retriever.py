import logging
from typing import TYPE_CHECKING, Optional

from redbot.core import commands

if TYPE_CHECKING:
    from aiuser.utils.vectorstore import VectorStore

logger = logging.getLogger("red.bz_cogs.aiuser")


class MemoryRetriever:
    """Handles retrieval of relevant memories using semantic similarity search."""

    def __init__(self, ctx: commands.Context, db: "VectorStore"):
        self.ctx = ctx
        self.db = db

    async def fetch_relevant(
        self, query: str, threshold: float = 0.75
    ) -> Optional[str]:
        """
        Fetch the most relevant memory based on a similarity threshold.

        Args:
            query: The text to search for similar memories
            threshold: Minimum similarity threshold for relevance (higher is more similar)

        Returns:
            The most relevant memory text if found and above threshold, None otherwise
        """
        if not query.strip():
            return None

        try:
            memory_results = await self.db.search_similar(query, self.ctx.guild.id, k=1)
        except Exception:
            logger.exception("Database error while searching memories")
            return None

        score = memory_results[0][2] if memory_results else 0

        logger.debug(
            f"Memory search score: {score:.3f} (threshold: {threshold}) for query: {query[:50]}..."
        )
        if score >= threshold:
            return f"Looking into your memory, the following relevant memory was found that could be used in the response: `{memory_results[0][1]}`"

        return None
