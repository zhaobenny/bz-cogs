import logging
from pathlib import Path
from typing import List, Optional, Tuple

from sentence_transformers import SentenceTransformer

from aiuser.config.constants import EMBEDDING_DB_NAME, EMBEDDING_MODEL
from aiuser.utils.sqlite3 import connect_db, serialize_f32

logger = logging.getLogger("red.bz_cogs.aiuser")


class MemoryRetriever:
    """Handles retrieval of relevant memories using semantic similarity search."""
    
    def __init__(self, cog_data_path: Path):
        self.cog_data_path = cog_data_path
        self._model: Optional[SentenceTransformer] = None
        self._db_path = cog_data_path / EMBEDDING_DB_NAME
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the SentenceTransformer model."""
        if self._model is None:
            self._model = SentenceTransformer(
                EMBEDDING_MODEL, 
                cache_folder=self.cog_data_path
            )
        return self._model
    
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
            
        # Generate embedding for the query
        query_embedding = self.model.encode(query)
        
        # Search for similar memories in the database
        memory_results = self._search_memories(query_embedding)
        
        # Return the most relevant memory formatted if it meets the threshold
        if memory_results and memory_results[0][3] < threshold:
            return f"Looking into your memory, the following most relevant memory was found: {memory_results[0][2]}"
        
        return None
    
    def _search_memories(self, query_embedding) -> List[Tuple]:
        """
        Search for memories in the database using vector similarity.
        
        Args:
            query_embedding: The encoded query vector
            
        Returns:
            List of tuples containing (rowid, memory_name, memory_text, distance)
        """
        try:
            with connect_db(self._db_path) as conn:
                results = conn.execute(
                    """
                    SELECT
                        rowid, memory_name, memory_text, 
                        distance
                    FROM memories
                    WHERE memory_vector MATCH ? and k=1
                    ORDER BY distance
                    """,
                    [serialize_f32(query_embedding)]
                ).fetchall()
                
            return results     
        except Exception as e:
            logger.error(f"Database error while searching memories: {e}")
            return []