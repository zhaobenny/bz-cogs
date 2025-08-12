import time

import sqlite_vec
from pysqlite3 import dbapi2 as sqlite3
from redbot.core import commands
from redbot.core.data_manager import cog_data_path
from sentence_transformers import SentenceTransformer

from aiuser.types.abc import MixinMeta, aiuser
from aiuser.utils.utilities import serialize_f32


class MemorySettings(MixinMeta):

    @aiuser.group(name="memory")
    @commands.has_permissions(manage_guild=True)
    async def memory(self, _):
        """ Manages long-term memory settings
            (All subcommands are per server)
        """
        pass

    @memory.command(name="list")
    async def list_memory(self, ctx: commands.Context):
        """Shows all memories stored."""
        db_path = cog_data_path(self) / "embeddings.db"
        db = sqlite3.connect(db_path)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)

        # Query all memories from the database
        cursor = db.execute("SELECT memory_name FROM memories")
        memories = cursor.fetchall()

        if not memories:
            await ctx.send("No memories found.")
            return

        # Prepare a formatted string to show the list of memories in markdown
        memory_list = "\n".join(
            [f"**{i+1}. `{mem[0]}`**\n" for i, mem in enumerate(memories)]
        )
        await ctx.send(f"**Stored memories**:\n{memory_list}")

    @memory.command(name="show")
    async def show_memory(self, ctx: commands.Context, memory_id: int):
        """Shows a memory by ID."""
        db_path = cog_data_path(self) / "embeddings.db"
        db = sqlite3.connect(db_path)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)

        # Query the memory by its ID (assumes 1-based index for user input)
        cursor = db.execute("SELECT memory_name, memory_text FROM memories LIMIT ?, 1", (memory_id - 1,))
        memory = cursor.fetchone()

        if not memory:
            await ctx.send(f"No memory found with ID {memory_id}.")
            return

        memory_name, memory_text = memory
        await ctx.send(f"**Memory {memory_id}:**\n**Name:** {memory_name}\n**Content:**\n```{memory_text}```")

    @memory.command(name="remove", aliases=["delete"])
    async def remove_memory(self, ctx: commands.Context, memory_id: int):
        """Removes a memory by ID."""
        db_path = cog_data_path(self) / "embeddings.db"
        db = sqlite3.connect(db_path)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)

        # Delete the memory by its ID (assumes 1-based index for user input)
        with db:
            db.execute("DELETE FROM memories WHERE rowid = ?", (memory_id,))

        await ctx.send(f"Memory {memory_id} successfully removed from the database.")

    @memory.command(name="add")
    async def add_memory(self, ctx: commands.Context, *, memory: str):
        """Adds a memory with its embedding where the format is `<MEMORY_NAME>: <MEMORY_CONTENT>`."""

        # Split the memory into the name and content
        memory_name, memory_text = memory.split(":", 1)

        # Load the embedding model
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", cache_folder=cog_data_path(self))

        # Generate an embedding for the input memory
        embedding = model.encode(memory_text)

        print(f"Embedding type: {type(embedding)}")
        print(f"Embedding shape: {embedding.shape}")

        await ctx.send(f"Memory added successfully with embedding of size {embedding.shape}.")

        db_path = cog_data_path(self) / "embeddings.db"
        db = sqlite3.connect(db_path)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)

        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories USING vec0(
                memory_name text,
                memory_vector float[384], 
                +memory_text text,
                last_updated integer
            )
        """)

        current_timestamp = int(time.time())
        with db:
            db.execute(
                "INSERT INTO memories(memory_vector, memory_name, memory_text, last_updated) VALUES (?, ?, ?, ?)",
                [serialize_f32(embedding.tolist()), memory_name, memory_text, current_timestamp],
            )

        await ctx.send("Memory successfully added to the database.")