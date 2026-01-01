import logging
import time

import discord
from redbot.core import commands
from redbot.core.utils.menus import SimpleMenu

from aiuser.types.abc import MixinMeta, aiuser
from aiuser.utils.utilities import encode_text_to_tokens

logger = logging.getLogger("red.bz_cogs.aiuser")


class MemorySettings(MixinMeta):
    @aiuser.group(name="memory")
    @commands.has_permissions(manage_guild=True)
    async def memory(self, _):
        """
        This feature is **WIP**! Manual memory creation / English is only supported for now.
        Breaking changes could happen! (such as losing all saved memories)

        Manages saved memory settings
        (All subcommands are per server)
        """
        pass

    @memory.command(name="toggle")
    @commands.has_permissions(manage_guild=True)
    async def toggle_memory_usage(self, ctx: commands.Context):
        """Enable/disable querying saved memories whenever responding to a message

        (Via just comparing semantic similarity of the previous message, no tool calling yet!)
        """

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

        try:
            memories = await self.db.list(ctx.guild.id)
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
            memory = await self.db.fetch_by_rowid(memory_id, ctx.guild.id)
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
            memory_id = await self.db.upsert(
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
            row = await self.db.fetch_by_rowid(memory_id, ctx.guild.id)
            if not row:
                embed = discord.Embed(
                    title="Memory Not Found!",
                    description=f"No memory found with ID `{memory_id}`.",
                    color=discord.Color.red(),
                )
                return await ctx.send(embed=embed)

            await self.db.delete(memory_id, ctx.guild.id)
        except Exception:
            logger.exception("Memory delete did not succeed")
            return await ctx.message.add_reaction("⚠️")

        embed = discord.Embed(
            title="Memory Removed",
            description=f"Sucessfuly removed memory #`{memory_id}` - `{row[0]}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
