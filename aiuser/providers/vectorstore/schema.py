import aiosqlite

CURRENT_SCHEMA_VERSION = 4

CREATE_MEMORIES_TABLE = """
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    memory_name TEXT NOT NULL,
    memory_text TEXT NOT NULL,
    embedding BLOB NOT NULL,
    user TEXT,
    channel TEXT
)
"""

CREATE_UNIQUE_INDEX = """
CREATE UNIQUE INDEX idx_memories_unique
ON memories (guild_id, memory_name, IFNULL(user, ''), IFNULL(channel, ''))
"""


async def _migrate_to_v4(conn: aiosqlite.Connection) -> None:
    cursor = await conn.execute("PRAGMA table_info(memories)")
    columns = {row[1] for row in await cursor.fetchall()}

    # Older migrations could advance user_version after only one of these
    # columns was added. Repair that state before rebuilding the table.
    if "user" not in columns:
        await conn.execute("ALTER TABLE memories ADD COLUMN user TEXT")
    if "channel" not in columns:
        await conn.execute("ALTER TABLE memories ADD COLUMN channel TEXT")

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

    await conn.execute(CREATE_MEMORIES_TABLE.replace("memories", "memories_v4", 1))
    await conn.execute(
        """
        INSERT INTO memories_v4 (
            id, guild_id, memory_name, memory_text, embedding, user, channel
        )
        SELECT
            rowid, guild_id, memory_name, memory_text, embedding, user, channel
        FROM memories
        """
    )
    await conn.execute("DROP TABLE memories")
    await conn.execute("ALTER TABLE memories_v4 RENAME TO memories")
    await conn.execute(CREATE_UNIQUE_INDEX)


async def ensure_sqlite_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = await conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'memories'"
            )
            if await cursor.fetchone() is None:
                await conn.execute(CREATE_MEMORIES_TABLE)
                await conn.execute(CREATE_UNIQUE_INDEX)
                await conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
                await conn.commit()
                return

            cursor = await conn.execute("PRAGMA user_version")
            current_version = (await cursor.fetchone())[0]

            if current_version < CURRENT_SCHEMA_VERSION:
                await _migrate_to_v4(conn)
                await conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
