from pathlib import Path
from typing import Optional, Union

import aiosqlite

from aiuser.config.constants import COMPACTION_DB_NAME
from aiuser.utils.compaction.schema import ensure_compaction_db


class CompactionStore:
    def __init__(self, cog_data_path: Union[str, Path]):
        self.cog_data_path = Path(cog_data_path)
        self.db_path = self.cog_data_path / COMPACTION_DB_NAME

    async def get_summary(self, guild_id: int, channel_id: int) -> Optional[str]:
        """Fetch the current compacted summary for a channel."""
        await ensure_compaction_db(str(self.db_path))

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT summary FROM compacted_messages WHERE guild_id = ? AND channel_id = ?",
                (guild_id, channel_id),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def upsert_summary(self, guild_id: int, channel_id: int, summary: str):
        """Update or insert the compacted summary for a channel."""
        await ensure_compaction_db(str(self.db_path))

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO compacted_messages (guild_id, channel_id, summary)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, channel_id) DO UPDATE SET summary = excluded.summary
                """,
                (guild_id, channel_id, summary),
            )
            await conn.commit()

    async def delete_summary(self, guild_id: int, channel_id: int):
        await ensure_compaction_db(str(self.db_path))

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "DELETE FROM compacted_messages WHERE guild_id = ? AND channel_id = ?",
                (guild_id, channel_id),
            )
            await conn.commit()
