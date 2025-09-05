import struct
from sqlite3 import Connection
from typing import List

import sqlite_vec
from pysqlite3 import dbapi2 as sqlite3


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
    
    conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_guild 
                ON memories(guild_id)
            """)
    
    return conn

def serialize_f32(vector: List[float]) -> bytes:
    """Serializes a list of floats into a compact "raw bytes" format."""
    return struct.pack("%sf" % len(vector), *vector)