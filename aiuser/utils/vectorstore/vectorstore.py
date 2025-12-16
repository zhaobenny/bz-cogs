import re
from pathlib import Path
from typing import List, Optional, Tuple, Union

import aiosqlite
import numpy as np
from rank_bm25 import BM25Okapi

from aiuser.config.constants import EMBEDDING_DB_NAME
from aiuser.utils.vectorstore.embeddings import embed_text
from aiuser.utils.vectorstore.schema import ensure_sqlite_db


class VectorStore:
    def __init__(self, cog_data_path: Union[str, Path]):
        self.cog_data_path = Path(cog_data_path)
        self.db_path = self.cog_data_path / EMBEDDING_DB_NAME

    async def _embed_text(self, text: str) -> bytes:
        embedding_array = await embed_text(text, str(self.cog_data_path))
        return np.array(embedding_array, dtype=np.float32).tobytes()

    async def upsert(
        self, guild_id: int, memory_name: str, memory_text: str, last_updated: int
    ) -> int:
        """Insert a new memory row. Returns number of rows in table after insert."""
        await self.create_memory(guild_id, memory_name, memory_text, last_updated)

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM memories WHERE guild_id = ?", (guild_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def create_memory(
        self, guild_id: int, memory_name: str, memory_text: str, last_updated: int
    ) -> int:
        """Insert a new memory row. Returns the rowid of the inserted row."""
        await ensure_sqlite_db(str(self.db_path))
        embedding_bytes = await self._embed_text(memory_text)

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO memories (guild_id, memory_name, memory_text, last_updated, embedding)
                VALUES (?, ?, ?, ?, ?)
                """,
                (guild_id, memory_name, memory_text, last_updated, embedding_bytes),
            )
            await conn.commit()
            return cursor.lastrowid

    async def update_memory(
        self,
        rowid: int,
        guild_id: int,
        memory_name: str,
        memory_text: str,
        last_updated: int,
    ) -> None:
        """Update an existing memory row by its rowid."""
        await ensure_sqlite_db(str(self.db_path))
        embedding_bytes = await self._embed_text(memory_text)

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE memories
                SET memory_name = ?, memory_text = ?, last_updated = ?, embedding = ?
                WHERE rowid = ? AND guild_id = ?
                """,
                (
                    memory_name,
                    memory_text,
                    last_updated,
                    embedding_bytes,
                    rowid,
                    guild_id,
                ),
            )
            await conn.commit()

    async def delete_memory_by_id(self, rowid: int, guild_id: int) -> bool:
        """Delete a memory by its rowid."""
        await ensure_sqlite_db(str(self.db_path))
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM memories WHERE rowid = ? AND guild_id = ?",
                (rowid, guild_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def list_memories_with_ids(
        self, guild_id: int, limit: int = 50
    ) -> List[Tuple[int, str, str]]:
        """List memories with their rowids, names, and text for a guild."""
        await ensure_sqlite_db(str(self.db_path))
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT rowid, memory_name, memory_text FROM memories WHERE guild_id = ? ORDER BY rowid ASC LIMIT ?",
                (guild_id, limit),
            )
            res = await cursor.fetchall()
        return res

    async def list(self, guild_id: int) -> List[Tuple[int, str]]:
        """List memory names for a guild."""
        await ensure_sqlite_db(str(self.db_path))
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT memory_name FROM memories WHERE guild_id = ? ORDER BY rowid ASC",
                (guild_id,),
            )
            res = await cursor.fetchall()

        if not res:
            return []
        return [(i + 1, r[0]) for i, r in enumerate(res)]

    async def fetch_by_rowid(
        self, rowid: int, guild_id: int
    ) -> Optional[Tuple[str, str]]:
        """Fetch a memory by its 1-based row index for the guild."""
        await ensure_sqlite_db(str(self.db_path))
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT memory_name, memory_text FROM memories WHERE guild_id = ? ORDER BY rowid ASC",
                (guild_id,),
            )
            res = await cursor.fetchall()

        if not res:
            return None

        idx = rowid - 1
        if idx < 0 or idx >= len(res):
            return None

        r = res[idx]
        return r[0], r[1]

    async def delete(self, rowid: int, guild_id: int) -> bool:
        """Delete a memory by its 1-based row index for the guild."""
        await ensure_sqlite_db(str(self.db_path))
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT rowid FROM memories WHERE guild_id = ? ORDER BY rowid ASC",
                (guild_id,),
            )
            rows = await cursor.fetchall()

            if not rows:
                return False

            idx = rowid - 1
            if idx < 0 or idx >= len(rows):
                return False

            target_rowid = rows[idx][0]

            await conn.execute("DELETE FROM memories WHERE rowid = ?", (target_rowid,))
            await conn.commit()
            return True

    async def search_similar(
        self, query: str, guild_id: int, k: int = 1
    ) -> List[Tuple[int, str, str, float]]:
        """Search for similar memories using BM25 pre-filtering + embedding similarity."""
        await ensure_sqlite_db(str(self.db_path))

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT rowid, memory_text FROM memories WHERE guild_id = ?",
                (guild_id,),
            )
            text_rows = await cursor.fetchall()

            if not text_rows:
                return []

            tokenized_corpus = [re.findall(r"\w+", row[1].lower()) for row in text_rows]
            bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = re.findall(r"\w+", query.lower())
            bm25_scores = bm25.get_scores(tokenized_query)

            top_indices = np.argsort(bm25_scores)[-50:][::-1]
            candidate_rowids = [text_rows[i][0] for i in top_indices]

            if not candidate_rowids:
                return []

            placeholders = ",".join("?" * len(candidate_rowids))
            cursor = await conn.execute(
                f"SELECT rowid, memory_name, memory_text, embedding FROM memories WHERE rowid IN ({placeholders})",
                candidate_rowids,
            )
            candidates = await cursor.fetchall()

        query_embedding = await embed_text(query, str(self.cog_data_path))

        similarities = []
        for rowid, name, text, emb_bytes in candidates:
            emb = np.frombuffer(emb_bytes, dtype=np.float32)
            score = np.dot(query_embedding, emb)
            similarities.append((rowid, name, text, float(score)))

        similarities.sort(key=lambda x: x[3], reverse=True)
        return similarities[:k]
