import asyncio
import logging
import struct
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
import sqlite_vec
import tiktoken
from fastembed import TextEmbedding
from fastembed.common.types import NumpyArray

from aiuser.config.constants import EMBEDDING_MODEL, FALLBACK_TOKENIZER
from aiuser.utils.utilities import encode_text_to_tokens

logger = logging.getLogger("red.bz_cogs.aiuser")


@asynccontextmanager
async def get_conn(path: str) -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(path)
    if not hasattr(conn, "enable_load_extension"):
        logger.exception(
            """Your Python's SQLite distribution may not be compiled with loadable extensions enabled.\n 
            This is required for sqlite-vec to work. Please refer to https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.enable_load_extension for more information."""
        )
        raise RuntimeError("SQLite loadable extensions are not enabled.")
    try:
        await conn.enable_load_extension(True)
        await conn.load_extension(sqlite_vec.loadable_path())
        await conn.enable_load_extension(False)

        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories USING vec0(
                guild_id integer,
                memory_name text,
                memory_vector float[384],
                memory_text text,
                last_updated integer
            )
        """)
        await conn.execute("PRAGMA user_version = 1;")
        await conn.commit()
        yield conn
    finally:
        await conn.close()


async def embed_text(text: str, cache_folder: Path) -> NumpyArray:
    token_count = await encode_text_to_tokens(text)
    if token_count > 512:
        text = await truncate_text_to_tokens(text, FALLBACK_TOKENIZER)
    model = TextEmbedding(EMBEDDING_MODEL, cache_folder=cache_folder)
    vec = await asyncio.to_thread(lambda: next(iter(model.embed([text]))))
    return vec.tolist()


async def truncate_text_to_tokens(text: str, max_tokens: int = 450) -> str:
    """Helper function to truncate text to specified number of tokens."""
    encoding = tiktoken.get_encoding(FALLBACK_TOKENIZER)

    def _truncate():
        tokens = encoding.encode(text)[:max_tokens]
        return encoding.decode(tokens)

    return await asyncio.to_thread(_truncate)


def serialize_f32(vector: list[float]) -> bytes:
    """Serializes a list of floats into a compact "raw bytes" format."""
    return struct.pack("%sf" % len(vector), *vector)
