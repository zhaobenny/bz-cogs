import aiosqlite

CURRENT_SCHEMA_VERSION = 3


async def ensure_sqlite_db(db_path: str):
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                guild_id INTEGER,
                memory_name TEXT,
                memory_text TEXT,
                last_updated INTEGER,
                embedding BLOB,
                user TEXT,
                channel TEXT
            )
            """
        )

        cursor = await conn.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        current_version = row[0] if row else 0

        if current_version < 2:
            try:
                await conn.execute("ALTER TABLE memories ADD COLUMN user TEXT")
                await conn.execute("ALTER TABLE memories ADD COLUMN channel TEXT")
            except aiosqlite.OperationalError:
                pass

        if current_version < 3:
            try:
                # deduplicate existing memories
                await conn.execute(
                    """
                    DELETE FROM memories
                    WHERE rowid NOT IN (
                        SELECT MAX(rowid)
                        FROM memories
                        GROUP BY guild_id, memory_name, IFNULL(user, ''), IFNULL(channel, '')
                    )
                    """
                )
                await conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_unique ON memories (guild_id, memory_name, IFNULL(user, ''), IFNULL(channel, ''))"
                )
            except aiosqlite.OperationalError:
                pass

        if current_version < CURRENT_SCHEMA_VERSION:
            await conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

        await conn.commit()
