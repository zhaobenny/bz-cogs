import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np

from aiuser.config.constants import EMBEDDING_DB_NAME
from aiuser.utils.utilities import to_thread
from aiuser.utils.vectorstore.embeddings import embed_text
from aiuser.utils.vectorstore.schema import ensure_sqlite_db


class VectorStore:
    def __init__(self, cog_data_path: Union[str, Path]):
        self.cog_data_path = Path(cog_data_path)
        self.db_path = self.cog_data_path / EMBEDDING_DB_NAME

    @to_thread()
    def _ensure_db(self):
        ensure_sqlite_db(str(self.db_path))

    @to_thread()
    def _upsert(self, guild_id: int, memory_name: str, memory_text: str, last_updated: int, embedding: bytes):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories (guild_id, memory_name, memory_text, last_updated, embedding)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, memory_name, memory_text, last_updated, embedding)
        )
        conn.commit()

        # Get count
        cursor.execute("SELECT COUNT(*) FROM memories WHERE guild_id = ?", (guild_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    async def upsert(
        self, guild_id: int, memory_name: str, memory_text: str, last_updated: int
    ) -> int:
        """Insert a new memory row. Returns number of rows in table after insert."""
        await self._ensure_db()

        embedding_array = await embed_text(memory_text, str(self.cog_data_path))
        embedding_bytes = np.array(embedding_array, dtype=np.float32).tobytes()

        return await self._upsert(guild_id, memory_name, memory_text, last_updated, embedding_bytes)

    @to_thread()
    def _list(self, guild_id: int) -> List[Tuple[int, str]]:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT memory_name FROM memories WHERE guild_id = ? ORDER BY rowid ASC",
            (guild_id,)
        )
        res = cursor.fetchall()
        conn.close()

        if not res:
            return []
        return [(i + 1, r[0]) for i, r in enumerate(res)]

    async def list(self, guild_id: int) -> List[Tuple[int, str]]:
        """List memory names for a guild."""
        await self._ensure_db()
        return await self._list(guild_id)

    @to_thread()
    def _fetch_by_rowid(self, rowid: int, guild_id: int) -> Optional[Tuple[str, str]]:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT memory_name, memory_text FROM memories WHERE guild_id = ? ORDER BY rowid ASC",
            (guild_id,)
        )
        res = cursor.fetchall()
        conn.close()

        if not res:
            return None

        idx = rowid - 1
        if idx < 0 or idx >= len(res):
            return None

        r = res[idx]
        return r[0], r[1]

    async def fetch_by_rowid(
        self, rowid: int, guild_id: int
    ) -> Optional[Tuple[str, str]]:
        """Fetch a memory by its 1-based row index for the guild."""
        await self._ensure_db()
        return await self._fetch_by_rowid(rowid, guild_id)

    @to_thread()
    def _delete(self, rowid: int, guild_id: int) -> bool:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get all rowids for the guild to find the correct one to delete
        cursor.execute(
            "SELECT rowid FROM memories WHERE guild_id = ? ORDER BY rowid ASC",
            (guild_id,)
        )
        rows = cursor.fetchall()

        if not rows:
            conn.close()
            return False

        idx = rowid - 1
        if idx < 0 or idx >= len(rows):
            conn.close()
            return False

        target_rowid = rows[idx][0]

        cursor.execute("DELETE FROM memories WHERE rowid = ?", (target_rowid,))
        conn.commit()
        conn.close()
        return True

    async def delete(self, rowid: int, guild_id: int) -> bool:
        """Delete a memory by its 1-based row index for the guild."""
        await self._ensure_db()
        return await self._delete(rowid, guild_id)

    @to_thread()
    def _search_similar(self, query_embedding: np.ndarray, guild_id: int, k: int) -> List[Tuple[str, str, float]]:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT memory_name, memory_text, embedding FROM memories WHERE guild_id = ?",
            (guild_id,)
        )
        res = cursor.fetchall()
        conn.close()

        if not res:
            return []

        # Cosine similarity calculation
        # fastembed returns normalized vectors (L2 norm = 1.0)
        # So Cosine Similarity = Dot Product (u . v) / (||u|| * ||v||) => (u . v) / 1 => u . v

        q = query_embedding

        similarities = []
        for name, text, emb_bytes in res:
            emb = np.frombuffer(emb_bytes, dtype=np.float32)
            score = np.dot(q, emb)
            similarities.append((name, text, float(score)))

        # Sort by score descending (highest similarity first)
        similarities.sort(key=lambda x: x[2], reverse=True)

        # Take top k
        top_k = similarities[:k]

        # The original code returned `dist`. If consumers expect distance, I might need to adjust.
        # But if I change it to SQLite + simple math, maybe the consumer logic needs to change too?
        # I'll check usages of `search_similar`.

        return top_k

    async def search_similar(
        self, query: str, guild_id: int, k: int = 1
    ) -> List[Tuple[str, str, float]]:
        """Search for similar memories using the provided embedding."""
        await self._ensure_db()
        query_embedding = await embed_text(query, str(self.cog_data_path))

        return await self._search_similar(query_embedding, guild_id, k)
