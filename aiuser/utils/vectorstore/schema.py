import lancedb
from lancedb.pydantic import LanceModel, Vector

SCHEMA_VERSION = 1
MEMORY_TABLE_NAME = "memories"


class MemoryModel(LanceModel):
    guild_id: int
    memory_name: str
    memory_text: str
    last_updated: int
    embedding: Vector(384)  # type: ignore[call-arg]


async def ensure_lance_db(db: lancedb.db.AsyncConnection) -> None:
    try:
        if MEMORY_TABLE_NAME in list(await db.table_names()):
            return
    except Exception:
        raise RuntimeError("Failed to validate LanceDB schema")

    await db.create_table(MEMORY_TABLE_NAME, schema=MemoryModel, exist_ok=False)

    mem_table = await db.open_table(MEMORY_TABLE_NAME)
    await mem_table.tags.create(str(SCHEMA_VERSION), await mem_table.version())
