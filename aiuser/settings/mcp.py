from __future__ import annotations

import re

import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import SimpleMenu

from aiuser.mcp.client import MCPError
from aiuser.settings.functions.utilities import functions
from aiuser.types.abc import MixinMeta


class MCPSettings(MixinMeta):
    @functions.group(name="mcp", invoke_without_command=True)
    async def mcp(self, ctx: commands.Context):
        """Configure remote MCP tool servers."""
        await ctx.send_help()

    @mcp.command(name="servers", aliases=["list"])
    async def mcp_servers(self, ctx: commands.Context):
        """List configured MCP servers."""
        servers = await self.config.mcp_servers()
        if not servers:
            return await ctx.send("No MCP servers are configured.")
        enabled = set(await self.config.guild(ctx.guild).mcp_enabled_servers())
        formatted_list = "\n".join(
            f"`{name}` {'Enabled' if name in enabled else 'Disabled'}"
            for name in sorted(servers)
        )
        pages = [
            discord.Embed(
                title="MCP servers",
                description=text,
                color=await ctx.embed_color(),
            )
            for text in pagify(formatted_list, page_length=888)
        ]
        if len(pages) == 1:
            return await ctx.send(embed=pages[0])

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i + 1} of {len(pages)}")
        return await SimpleMenu(pages).start(ctx)

    @mcp.command(name="add")
    async def mcp_add(self, ctx: commands.Context, name: str, url: str):
        """Add an MCP server to the bot-wide catalog.
        """
        if not re.fullmatch(r"[a-z0-9_-]{1,32}", name):
            return await ctx.send(
                "Server names must use 1-32 lowercase letters, numbers, `_`, or `-`."
            )
        servers = await self.config.mcp_servers()
        if name in servers:
            return await ctx.send(f"MCP server `{name}` already exists.")
        servers[name] = {"url": url}
        await self.config.mcp_servers.set(servers)
        embed = discord.Embed(
            title="MCP server added",
            description=f"`{name}`\n`{url}`",
            color=await ctx.embed_color(),
        )
        embed.add_field(
            name="Next steps",
            value=(
                "If this server requires HTTP Bearer authentication, set its token first:\n"
                f"`{ctx.clean_prefix}set api mcp_{name} token,VALUE`\n\n"
                "Enable it for this Discord server:\n"
                f"`{ctx.clean_prefix}aiuser tools mcp enable {name}`"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @mcp.command(name="url")
    async def mcp_url(self, ctx: commands.Context, name: str, url: str):
        """Reconfigure the URL a MCP server uses."""
        servers = await self.config.mcp_servers()
        if name not in servers:
            return await ctx.send(f"Unknown MCP server `{name}`.")
        servers[name]["url"] = url
        await self.config.mcp_servers.set(servers)
        await self.services.mcp.invalidate_server(name)
        embed = discord.Embed(
            title="MCP server URL updated",
            description=f"`{name}`",
            color=await ctx.embed_color(),
        )
        embed.add_field(name="URL", value=f"`{url}`", inline=False)
        await ctx.send(embed=embed)

    @mcp.command(name="remove", aliases=["delete"])
    async def mcp_remove(self, ctx: commands.Context, name: str):
        """Remove an MCP server from the bot-wide catalog."""
        servers = await self.config.mcp_servers()
        if name not in servers:
            return await ctx.send(f"Unknown MCP server `{name}`.")
        servers.pop(name)
        await self.config.mcp_servers.set(servers)
        for guild_id, data in (await self.config.all_guilds()).items():
            enabled = data.get("mcp_enabled_servers", [])
            if name in enabled:
                await self.config.guild_from_id(guild_id).mcp_enabled_servers.set([
                    server_alias for server_alias in enabled if server_alias != name
                ])
        await self.services.mcp.invalidate_server(name)
        embed = discord.Embed(
            title="MCP server removed",
            description=f"`{name}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @mcp.command(name="info")
    async def mcp_info(self, ctx: commands.Context, name: str):
        """Show info on the configured MCP server."""
        server = (await self.config.mcp_servers()).get(name)
        if not server:
            return await ctx.send(f"Unknown MCP server `{name}`.")
        token = (await self.bot.get_shared_api_tokens(f"mcp_{name}")).get("token")
        enabled = name in await self.config.guild(ctx.guild).mcp_enabled_servers()
        try:
            tools = await self.services.mcp.tools_for_server(
                ctx.guild.id, name, server, refresh=True
            )
            connection = "Connected"
        except MCPError as exc:
            tools = []
            connection = f"Failed: {exc}"
        embed = discord.Embed(
            title=f"{name} MCP server settings",
            color=await ctx.embed_color(),
        )
        embed.add_field(name="Enabled", value="✅" if enabled else "❌")
        embed.add_field(name="Authentication", value="✅" if token else "❌")
        embed.add_field(
            name="Connection",
            value=(
                f"🟢 {connection}" if connection == "Connected" else f"🔴 {connection}"
            ),
            inline=False,
        )
        embed.add_field(name="URL", value=f"`{server['url']}`", inline=False)
        if tools:
            preview = "\n".join(tool.native_name[:100] for tool in tools[:8])
            if len(tools) > 8:
                preview += f"\n... and {len(tools) - 8} more"
            embed.add_field(
                name=f"Tools ({len(tools)})", value=box(preview), inline=False
            )
        elif connection == "Connected":
            embed.add_field(name="Tools", value="None", inline=False)
        await ctx.send(embed=embed)

    @mcp.command(name="enable")
    async def mcp_enable(self, ctx: commands.Context, name: str):
        """Enable an MCP server for this server."""
        servers = await self.config.mcp_servers()
        if name not in servers:
            return await ctx.send(f"Unknown MCP server `{name}`.")
        try:
            tools = await self.services.mcp.tools_for_server(
                ctx.guild.id, name, servers[name], refresh=True
            )
        except MCPError as exc:
            embed = discord.Embed(
                title=f"Could not enable {name} MCP server",
                description=str(exc),
                color=await ctx.embed_color(),
            )
            return await ctx.send(embed=embed)
        enabled = await self.config.guild(ctx.guild).mcp_enabled_servers()
        if name not in enabled:
            enabled.append(name)
            await self.config.guild(ctx.guild).mcp_enabled_servers.set(enabled)
        await self.config.guild(ctx.guild).function_calling.set(True)
        embed = discord.Embed(
            title=f"{name} MCP server is now:",
            description=f"Enabled with `{len(tools)}` tools",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @mcp.command(name="disable")
    async def mcp_disable(self, ctx: commands.Context, name: str):
        """Disable an MCP server for this server."""
        if name not in await self.config.mcp_servers():
            return await ctx.send(f"Unknown MCP server `{name}`.")
        enabled = await self.config.guild(ctx.guild).mcp_enabled_servers()
        if name in enabled:
            await self.config.guild(ctx.guild).mcp_enabled_servers.set([
                server_alias for server_alias in enabled if server_alias != name
            ])
        await self.services.mcp.invalidate(ctx.guild.id, name)
        embed = discord.Embed(
            title=f"{name} MCP server is now:",
            description="Disabled",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
