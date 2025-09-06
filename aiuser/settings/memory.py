import logging
import time

import discord
from redbot.core import commands
from redbot.core.data_manager import cog_data_path
from redbot.core.utils.menus import SimpleMenu

from aiuser.config.constants import EMBEDDING_DB_NAME
from aiuser.types.abc import MixinMeta, aiuser
from aiuser.utils.embeddings import embed_text, get_conn, serialize_f32
from aiuser.utils.utilities import encode_text_to_tokens

logger = logging.getLogger("red.bz_cogs.aiuser")


class MemorySettings(MixinMeta):
    @aiuser.group(name="memory")
    @commands.has_permissions(manage_guild=True)
    async def memory(self, _):
        """
        **This feature is WIP!
        Breaking changes could happen! (such as losing all saved memories)**

        Manages saved memory settings
        (All subcommands are per server)
        """
        pass

    @memory.command(name="toggle")
    @commands.has_permissions(manage_guild=True)
    async def toggle_memory_usage(self, ctx: commands.Context):
        """Enable/disable querying saved memories whenever responding to a message"""
        current = await self.config.guild(ctx.guild).query_memories()
        new_value = not current
        await self.config.guild(ctx.guild).query_memories.set(new_value)
        embed = discord.Embed(
            title="Querying of saved memories for this server now set to:",
            description=f"{new_value}",
            color=await ctx.embed_color(),
        )
        embed.set_footer(
            text="This feature is WIP! Breaking changes could happen! (such as losing all saved memories)"
        )
        await ctx.send(embed=embed)

    @memory.command(name="list")
    async def list_memory(self, ctx: commands.Context):
        """Shows all memories stored."""
        async with get_conn(cog_data_path(self) / EMBEDDING_DB_NAME) as conn:
            cursor = await conn.execute(
                "SELECT rowid, memory_name FROM memories WHERE guild_id = ? ORDER BY rowid",
                (ctx.guild.id,),
            )
            memories = await cursor.fetchall()

        if not memories:
            embed = discord.Embed(
                title="No Memories Found",
                color=await ctx.embed_color(),
            )
            return await ctx.send(embed=embed)

        memories_per_page = 15
        total_pages = (len(memories) - 1) // memories_per_page + 1

        # Single page: no footer, no menu
        if total_pages == 1:
            memory_list = "\n".join(
                f"**{rowid}.** `{name}`" for rowid, name in memories
            )
            embed = discord.Embed(
                title="📚 Stored Memories",
                description=memory_list,
                color=await ctx.embed_color(),
            )
            return await ctx.send(embed=embed)

        # Multiple pages: build embeds with footer and use SimpleMenu
        pages = []
        for i in range(0, len(memories), memories_per_page):
            page_memories = memories[i : i + memories_per_page]
            memory_list = "\n".join(
                f"**{rowid}.** `{name}`" for rowid, name in page_memories
            )

            embed = discord.Embed(
                title="📚 Stored Memories",
                description=memory_list,
                color=await ctx.embed_color(),
            )
            embed.set_footer(text=f"Page {i // memories_per_page + 1}/{total_pages}")
            pages.append(embed)

        await SimpleMenu(pages).start(ctx)

    @memory.command(name="show")
    async def show_memory(self, ctx: commands.Context, memory_id: int):
        """Shows a memory by ID."""
        async with get_conn(cog_data_path(self) / EMBEDDING_DB_NAME) as conn:
            cursor = await conn.execute(
                "SELECT memory_name, memory_text FROM memories WHERE rowid = ? AND guild_id = ?",
                (memory_id, ctx.guild.id),
            )
            memory = await cursor.fetchone()

        if not memory:
            embed = discord.Embed(
                title="Memory Not Found",
                description=f"No memory found with ID {memory_id}.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        memory_name, memory_text = memory

        if len(memory_text) > 1900:
            chunks = [
                memory_text[i : i + 1900] for i in range(0, len(memory_text), 1900)
            ]
            pages = []

            for i, chunk in enumerate(chunks):
                embed = discord.Embed(
                    title=f"Memory #`{memory_id}`: `{memory_name}`",
                    description=f"```{chunk}```",
                    color=await ctx.embed_color(),
                )
                embed.set_footer(text=f"Page {i + 1}/{len(chunks)}")
                pages.append(embed)

            await SimpleMenu(pages).start(ctx)
        else:
            embed = discord.Embed(
                title=f"Memory #`{memory_id}`: `{memory_name}`",
                description=f"```{memory_text}```",
                color=await ctx.embed_color(),
            )
            await ctx.send(embed=embed)

    @memory.command(name="add")
    async def add_memory(self, ctx: commands.Context, *, memory: str):
        """Adds a memory where the format is `<MEMORY_NAME>: <MEMORY_CONTENT>`."""
        if ":" not in memory:
            embed = discord.Embed(
                title="Invalid Format",
                description="Please use the format: `<MEMORY_NAME>: <MEMORY_CONTENT>`",
                color=discord.Color.red(),
            )
            return await ctx.send(embed=embed)

        # Split the memory into the name and content
        memory_name, memory_text = memory.split(":", 1)
        memory_name = memory_name.strip()
        memory_text = memory_text.strip()

        if await encode_text_to_tokens(memory_text) > 512:
            embed = discord.Embed(
                title="Memory too long!",
                description="Please use a shorter memory!\nMemory text longer than 512 tokens are currently not supported yet.",
                color=discord.Color.red(),
            )
            return await ctx.send(embed=embed)

        # Generate an embedding for the input memory
        embedding = await embed_text(memory_text, cog_data_path(self))

        current_timestamp = int(time.time())
        async with get_conn(cog_data_path(self) / EMBEDDING_DB_NAME) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO memories (guild_id, memory_vector, memory_name, memory_text, last_updated)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    ctx.guild.id,
                    serialize_f32(embedding),
                    memory_name,
                    memory_text,
                    current_timestamp,
                ),
            )
            memory_id = cursor.lastrowid
            await conn.commit()

            embed = discord.Embed(
                title="Memory Added",
                description=f"Successfully added memory: #`{memory_id}` - `{memory_name}` ",
                color=await ctx.embed_color(),
            )
            embed.set_footer(
                text="This feature is WIP! Breaking changes could happen! (such as losing all saved memories)"
            )
            return await ctx.send(embed=embed)

    @memory.command(name="remove", aliases=["delete"])
    async def remove_memory(self, ctx: commands.Context, memory_id: int):
        """Removes a memory by ID."""
        async with get_conn(cog_data_path(self) / EMBEDDING_DB_NAME) as conn:
            cursor = await conn.execute(
                "SELECT memory_name FROM memories WHERE rowid = ? AND guild_id = ?",
                (memory_id, ctx.guild.id),
            )
            row = await cursor.fetchone()

            if not row:
                embed = discord.Embed(
                    title="Memory Not Found!",
                    description=f"No memory found with ID `{memory_id}`.",
                    color=discord.Color.red(),
                )
                return await ctx.send(embed=embed)

            await conn.execute(
                "DELETE FROM memories WHERE rowid = ? AND guild_id = ?",
                (memory_id, ctx.guild.id),
            )
            await conn.commit()

        embed = discord.Embed(
            title="Memory Removed",
            description=f"Sucessfuly removed memory #`{memory_id}` - `{row[0]}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
