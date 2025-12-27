import aiosqlite

CURRENT_SCHEMA_VERSION = 1


async def ensure_sqlite_db(db_path: str):
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                guild_id INTEGER,
                memory_name TEXT,
                memory_text TEXT,
                last_updated INTEGER,
                embedding BLOB
            )
            """
        )
        await conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        await conn.commit()
