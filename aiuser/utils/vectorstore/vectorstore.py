from pathlib import Path
from typing import List, Optional, Tuple, Union

import lancedb
import numpy as np

from aiuser.config.constants import EMBEDDING_DB_NAME
from aiuser.utils.vectorstore.embeddings import embed_text
from aiuser.utils.vectorstore.schema import MEMORY_TABLE_NAME, ensure_lance_db


class VectorStore:
    def __init__(self, cog_data_path: Union[str, Path]):
        self.cog_data_path = Path(cog_data_path)
        self.db: Optional[lancedb.db.AsyncConnection] = None

    async def _connect(self):
        if self.db is None or (not self.db.is_open()):
            db_path = self.cog_data_path / EMBEDDING_DB_NAME
            conn = await lancedb.connect_async(str(db_path))
            await ensure_lance_db(conn)
            self.db = conn
        else:
            return

    async def upsert(
        self, guild_id: int, memory_name: str, memory_text: str, last_updated: int
    ) -> int:
        """Insert a new memory row. Returns number of rows in table after insert."""
        await self._connect()

        table = await self.db.open_table(MEMORY_TABLE_NAME)

        embedding = await embed_text(memory_text, str(self.cog_data_path))
        arr = np.array(embedding, dtype=np.float32).tolist()

        data = [
            {
                "guild_id": int(guild_id),
                "memory_name": memory_name,
                "memory_text": memory_text,
                "last_updated": int(last_updated),
                "embedding": arr,
            }
        ]

        await table.add(data)
        try:
            new_len = await table.count_rows()
        except Exception:
            return 1
        return int(new_len)

    async def list(self, guild_id: int) -> List[Tuple[int, str]]:
        """List memory names for a guild."""
        await self._connect()

        table = await self.db.open_table(MEMORY_TABLE_NAME)

        res = await (
            table.query()
            .where(f"guild_id = {int(guild_id)}")
            .select(["memory_name"])
            .to_list()
        )

        if not res:
            return []
        return [(i + 1, r.get("memory_name")) for i, r in enumerate(res)]

    async def fetch_by_rowid(
        self, rowid: int, guild_id: int
    ) -> Optional[Tuple[str, str]]:
        """Fetch a memory by its 1-based row index for the guild."""
        await self._connect()

        try:
            table = await self.db.open_table(MEMORY_TABLE_NAME)
        except FileNotFoundError:
            return None

        res = await (
            table.query()
            .where(f"guild_id = {int(guild_id)}")
            .select(["memory_name", "memory_text"])
            .to_list()
        )
        if not res:
            return None
        idx = rowid - 1
        if idx < 0 or idx >= len(res):
            return None
        r = res[idx]
        return r.get("memory_name"), r.get("memory_text")

    async def delete(self, rowid: int, guild_id: int) -> bool:
        """Delete a memory by its 1-based row index for the guild."""
        await self._connect()
        try:
            table = await self.db.open_table(MEMORY_TABLE_NAME)
        except FileNotFoundError:
            return False

        rows = await (
            table.query()
            .where(f"guild_id = {int(guild_id)}")
            .with_row_id()
            .select(["_rowid", "memory_name"])
            .to_list()
        )
        if not rows:
            return False
        idx = rowid - 1
        if idx < 0 or idx >= len(rows):
            return False
        target = rows[idx]
        global_rowid = target.get("_rowid")
        if global_rowid is None:
            return False

        await table.delete(f"_rowid = {int(global_rowid)}")
        return True

    async def search_similar(
        self, query: str, guild_id: int, k: int = 1
    ) -> List[Tuple[str, str, float]]:
        """Search for similar memories using the provided embedding."""
        await self._connect()
        query_embedding = await embed_text(query, str(self.cog_data_path))
        table = await self.db.open_table(MEMORY_TABLE_NAME)

        q = np.array(query_embedding, dtype=np.float32).tolist()

        res = await (
            (await table.search(q))
            .where(f"guild_id = {int(guild_id)}")
            .limit(k)
            .with_row_id()
            .select(["_rowid", "memory_name", "memory_text", "_distance"])
            .to_list()
        )

        out: List[Tuple[str, str, float]] = []
        for row in res:
            name = row.get("memory_name")
            text = row.get("memory_text")
            dist = float(row.get("_distance"))
            out.append((name, text, dist))
        return out
