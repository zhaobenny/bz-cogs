from pathlib import Path
from typing import List, Optional, Tuple, Union

import aiosqlite
import numpy as np

from aiuser.config.constants import EMBEDDING_CACHE_DIR_NAME, EMBEDDING_DB_NAME
from aiuser.providers.vectorstore.embeddings import embed_text


class VectorStore:
    def __init__(self, cog_data_path: Union[str, Path]):
        data_path = Path(cog_data_path)
        self.db_path = data_path / EMBEDDING_DB_NAME
        self.cache_path = data_path / EMBEDDING_CACHE_DIR_NAME

    async def upsert(
        self,
        guild_id: int,
        memory_name: str,
        memory_text: str,
        user: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> int:
        """Insert or update a memory and return its stable database ID."""
        for scope_name, scope_id in (("user", user), ("channel", channel)):
            if scope_id is not None and not (scope_id.isascii() and scope_id.isdigit()):
                raise ValueError(f"{scope_name} scope must be a Discord ID")

        embedding_bytes = (
            await embed_text(memory_text, str(self.cache_path))
        ).tobytes()

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO memories (guild_id, memory_name, memory_text, embedding, user, channel)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (guild_id, memory_name, IFNULL(user, ''), IFNULL(channel, ''))
                DO UPDATE SET
                    memory_text = excluded.memory_text,
                    embedding = excluded.embedding
                """,
                (
                    guild_id,
                    memory_name,
                    memory_text,
                    embedding_bytes,
                    user,
                    channel,
                ),
            )
            cursor = await conn.execute(
                """
                SELECT id FROM memories
                WHERE guild_id = ? AND memory_name = ?
                  AND user IS ? AND channel IS ?
                """,
                (guild_id, memory_name, user, channel),
            )
            memory_id = (await cursor.fetchone())[0]
            await conn.commit()
            return memory_id

    async def list(self, guild_id: int) -> List[Tuple[int, str]]:
        """List memory names for a guild."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT id, memory_name FROM memories WHERE guild_id = ? ORDER BY id ASC",
                (guild_id,),
            )
            res = await cursor.fetchall()

        return [(r[0], r[1]) for r in res]

    async def fetch_by_id(
        self, memory_id: int, guild_id: int
    ) -> Optional[Tuple[str, str]]:
        """Fetch a memory by its stable database ID for the guild."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT memory_name, memory_text FROM memories WHERE id = ? AND guild_id = ?",
                (memory_id, guild_id),
            )
            row = await cursor.fetchone()
        return (row[0], row[1]) if row else None

    async def delete(self, memory_id: int, guild_id: int) -> bool:
        """Delete a memory by its stable database ID for the guild."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM memories WHERE id = ? AND guild_id = ?",
                (memory_id, guild_id),
            )
            await conn.commit()
            return bool(cursor.rowcount)

    async def delete_user_memories(
        self, user_id: int, guild_id: Optional[int] = None
    ) -> int:
        """Delete memories scoped to a specific Discord user ID."""
        query = "DELETE FROM memories WHERE user = ?"
        params = [str(user_id)]

        if guild_id is not None:
            query += " AND guild_id = ?"
            params.append(guild_id)

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(query, params)
            await conn.commit()
            return cursor.rowcount

    async def search_similar(
        self,
        query: str,
        guild_id: int,
        k: int = 1,
        user: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> List[Tuple[str, str, float]]:
        """Search all in-scope memories using embedding similarity."""
        where_clause = "guild_id = ?"
        params = [guild_id]

        if user:
            where_clause += " AND (user = ? OR user IS NULL)"
            params.append(user)
        if channel:
            where_clause += " AND (channel = ? OR channel IS NULL)"
            params.append(channel)

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                f"SELECT memory_name, memory_text, embedding FROM memories WHERE {where_clause}",
                tuple(params),
            )
            candidates = await cursor.fetchall()

        if not candidates:
            return []

        query_embedding = await embed_text(query, str(self.cache_path))

        similarities = []
        for name, text, emb_bytes in candidates:
            emb = np.frombuffer(emb_bytes, dtype=np.float32)
            score = np.dot(query_embedding, emb)
            similarities.append((name, text, float(score)))

        similarities.sort(key=lambda x: x[2], reverse=True)
        return similarities[:k]
