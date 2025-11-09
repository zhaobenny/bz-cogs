import logging
from pathlib import Path
from typing import Optional

from redbot.core import commands

from aiuser.utils.vectorstore.repository import Repository

logger = logging.getLogger("red.bz_cogs.aiuser")


class MemoryRetriever:
    """Handles retrieval of relevant memories using semantic similarity search."""

    def __init__(self, cog_data_path: Path, ctx: commands.Context):
        self.cog_data_path = cog_data_path
        self.ctx = ctx

    async def fetch_relevant(self, query: str, threshold: float = 1.1) -> Optional[str]:
        """
        Fetch the most relevant memory based on a similarity threshold.

        Args:
            query: The text to search for similar memories
            threshold: Maximum distance threshold for relevance (lower is more similar)

        Returns:
            The most relevant memory text if found and below threshold, None otherwise
        """
        if not query.strip():
            return None

        try:
            repo = Repository(self.cog_data_path)
            memory_results = await repo.search_similar(query, self.ctx.guild.id, k=1)
        except Exception:
            logger.exception("Database error while searching memories")
            return None
        
        if memory_results and memory_results[0][2] < threshold:
            return f"Looking into your memory, the following most relevant memory was found: {memory_results[0][2]}"

        return None
