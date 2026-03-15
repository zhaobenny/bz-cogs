import aiosqlite

CURRENT_SCHEMA_VERSION = 1


async def ensure_compaction_db(db_path: str):
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS compacted_messages (
                guild_id INTEGER,
                channel_id INTEGER,
                summary TEXT,
                UNIQUE(guild_id, channel_id)
            )
            """
        )
        await conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        await conn.commit()
