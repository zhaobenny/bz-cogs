import asyncio
import struct
from pathlib import Path
from sqlite3 import Connection
from typing import List

import sqlite_vec
from fastembed import TextEmbedding
from pysqlite3 import dbapi2 as sqlite3

from aiuser.config.constants import EMBEDDING_MODEL


def connect_db(path: str) -> Connection:
    conn = sqlite3.connect(path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    # TODO: schema once
    conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories USING vec0(
                    guild_id integer,
                    memory_name text,
                    memory_vector float[384], 
                    +memory_text text,
                    last_updated integer
                )
            """)
    conn.execute("PRAGMA user_version = 1;")
    return conn


async def embed_text(query: str, cache_folder: Path) -> List[float]:
    model = TextEmbedding(EMBEDDING_MODEL, cache_folder=cache_folder)
    vecs = await asyncio.to_thread(lambda: list(model.embed([query])))
    return vecs


def serialize_f32(vector: List[float]) -> bytes:
    """Serializes a list of floats into a compact "raw bytes" format."""
    return struct.pack("%sf" % len(vector), *vector)
