import logging
import time

import discord
from redbot.core import commands
from redbot.core.utils.menus import SimpleMenu

from aiuser.settings._groups import aiuser
from aiuser.types.abc import MixinMeta
from aiuser.utils.utilities import encode_text_to_tokens

logger = logging.getLogger("red.bz_cogs.aiuser.memory")


class MemorySettings(MixinMeta):
    @aiuser.group(name="memory")
    @commands.has_permissions(manage_guild=True)
    async def memory(self, _):
        """
        Manages memory settings
        (All subcommands are per server)
        """
        pass

    @memory.command(name="status")
    async def memory_status(self, ctx: commands.Context):
        """Show whether saved memories are included in responses"""
        enabled = await self.config.guild(ctx.guild).query_memories()
        return await ctx.send(f"Saved memory retrieval enabled: `{enabled}`")

    @memory.command(name="enable")
    async def memory_enable(self, ctx: commands.Context):
        """Include relevant saved memories in responses"""
        await self.config.guild(ctx.guild).query_memories.set(True)
        return await ctx.send("Saved memory retrieval enabled.")

    @memory.command(name="disable")
    async def memory_disable(self, ctx: commands.Context):
        """Stop including saved memories in responses"""
        await self.config.guild(ctx.guild).query_memories.set(False)
        return await ctx.send("Saved memory retrieval disabled.")

    @memory.command(name="list")
    async def list_memory(self, ctx: commands.Context):
        """Shows all memories stored."""

        try:
            memories = await self.services.memories.list(ctx.guild.id)
        except Exception:
            logger.exception("Memory listing did not succeed")
            return await ctx.message.add_reaction("⚠️")

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

        try:
            memory = await self.services.memories.fetch_by_rowid(
                memory_id, ctx.guild.id
            )
        except Exception:
            logger.exception("Memory fetch did not succeed")
            return await ctx.message.add_reaction("⚠️")

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
        """Adds a memory where the format is `<MEMORY_NAME>: <MEMORY_CONTENT>`"""

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

        if await encode_text_to_tokens(memory_text) > 500:
            embed = discord.Embed(
                title="Memory too long!",
                description="Please use a shorter memory text!\nMemory text longer than 500 tokens are currently not supported yet.",
                color=discord.Color.red(),
            )
            return await ctx.send(embed=embed)

        current_timestamp = int(time.time())
        try:
            memory_id = await self.services.memories.upsert(
                ctx.guild.id,
                memory_name,
                memory_text,
                current_timestamp,
            )

            embed = discord.Embed(
                title="Memory Added",
                description=f"Successfully added memory: #`{memory_id}` - `{memory_name}` ",
                color=await ctx.embed_color(),
            )
            embed.set_footer(
                text="This feature is WIP! Breaking changes could happen! (such as losing all saved memories)"
            )
            return await ctx.send(embed=embed)
        except Exception:
            logger.exception("Memory insert did not succeed")
            return await ctx.message.add_reaction("⚠️")

    @memory.command(name="remove", aliases=["delete"])
    async def remove_memory(self, ctx: commands.Context, memory_id: int):
        """Removes a memory by ID."""

        try:
            row = await self.services.memories.fetch_by_rowid(memory_id, ctx.guild.id)
            if not row:
                embed = discord.Embed(
                    title="Memory Not Found!",
                    description=f"No memory found with ID `{memory_id}`.",
                    color=discord.Color.red(),
                )
                return await ctx.send(embed=embed)

            await self.services.memories.delete(memory_id, ctx.guild.id)
        except Exception:
            logger.exception("Memory delete did not succeed")
            return await ctx.message.add_reaction("⚠️")

        embed = discord.Embed(
            title="Memory Removed",
            description=f"Sucessfuly removed memory #`{memory_id}` - `{row[0]}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
