import sqlite3

def ensure_sqlite_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
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
    conn.commit()
    conn.close()
