import aiosqlite

CURRENT_SCHEMA_VERSION = 2


async def ensure_compaction_db(db_path: str):
    async with aiosqlite.connect(db_path) as conn:
        version = await conn.execute("PRAGMA user_version")
        current_version = (await version.fetchone())[0]

        if current_version < 1:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compacted_messages (
                    guild_id INTEGER,
                    channel_id INTEGER,
                    summary TEXT,
                    last_compacted_message_id INTEGER,
                    UNIQUE(guild_id, channel_id)
                )
                """
            )
        elif current_version < 2:
            # Migration: add new column to existing table
            try:
                await conn.execute(
                    "ALTER TABLE compacted_messages ADD COLUMN last_compacted_message_id INTEGER"
                )
            except Exception:
                pass  # Column may already exist

        await conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        await conn.commit()
