from __future__ import annotations

import re

import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import SimpleMenu

from aiuser.mcp.client import MCPAuthError, MCPError, MCPOAuthRequired
from aiuser.mcp.view import MCPAuthView
from aiuser.settings.functions.utilities import functions
from aiuser.types.abc import MixinMeta


class MCPSettings(MixinMeta):
    @functions.group(name="mcp", invoke_without_command=True)
    async def mcp(self, ctx: commands.Context):
        """Configure remote MCP tool servers."""
        await ctx.send_help()

    @mcp.command(name="servers", aliases=["list"])
    async def mcp_servers(self, ctx: commands.Context):
        """List configured MCP servers and if they are currenlty enabled for the current Discord server."""
        servers = await self.config.mcp_servers()
        if not servers:
            return await ctx.send("No MCP servers are configured.")
        enabled = set(await self.config.guild(ctx.guild).mcp_enabled_servers())
        enabled_pages = list(
            pagify(
                "\n".join(
                    f"✅ `{name}`" for name in sorted(servers) if name in enabled
                ),
                page_length=888,
            )
        ) or ["None"]
        disabled_pages = list(
            pagify(
                "\n".join(
                    f"❌ `{name}`" for name in sorted(servers) if name not in enabled
                ),
                page_length=888,
            )
        ) or ["None"]
        pages = []
        for page_number in range(max(len(enabled_pages), len(disabled_pages))):
            page = discord.Embed(
                title="Available MCP servers",
                color=await ctx.embed_color(),
            )
            if page_number < len(enabled_pages):
                page.add_field(name="Enabled", value=enabled_pages[page_number])
            if page_number < len(disabled_pages):
                page.add_field(name="Disabled", value=disabled_pages[page_number])
            pages.append(page)
        if len(pages) == 1:
            return await ctx.send(embed=pages[0])

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i + 1} of {len(pages)}")
        return await SimpleMenu(pages).start(ctx)

    @mcp.command(name="add")
    async def mcp_add(self, ctx: commands.Context, name: str, url: str):
        """Add an MCP server to the catalog of avaiable servers to use."""
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
            title="Added MCP server",
            color=await ctx.embed_color(),
        )
        embed.add_field(name="Name", value=f"`{name}`", inline=False)
        embed.add_field(name="URL", value=f"`{url}`", inline=False)
        embed.add_field(
            name="Authentication",
            value=(
                "The added MCP server may require `oAuth` or `Bearer` token authentication. "
                "Please select the appropriate option below to authenticate the bot with the MCP server."
            ),
            inline=False,
        )
        embed.set_footer(text="The MCP server will need enabling per Discord server.")
        try:
            await self.services.mcp.tools_for_mcp_server(
                ctx.guild.id, name, servers[name], refresh=True
            )
        except MCPOAuthRequired as exc:
            view = MCPAuthView(
                self.services.mcp,
                name,
                ctx.author.id,
                ctx.guild.id,
                url,
                exc.challenge,
            )
            view.message = await ctx.send(embed=embed, view=view)
            return
        except MCPError as exc:
            embed.add_field(
                name="Connection",
                value=f"{exc}\nRemove and add this server again to retry authentication.",
                inline=False,
            )
        await ctx.send(embed=embed)

    @mcp.command(name="url")
    async def mcp_url(self, ctx: commands.Context, name: str, url: str):
        """Reconfigure the URL a MCP server uses."""
        servers = await self.config.mcp_servers()
        if name not in servers:
            return await ctx.send(f"Unknown MCP server `{name}`.")
        await self.services.mcp.oauth.forget(name)
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
        """Remove an MCP server by name from the available catalog."""
        servers = await self.config.mcp_servers()
        if name not in servers:
            return await ctx.send(f"Unknown MCP server `{name}`.")
        await self.services.mcp.oauth.forget(name)
        await self.bot.remove_shared_api_tokens(f"mcp_{name}", "token")
        servers.pop(name)
        await self.config.mcp_servers.set(servers)
        for guild_id, data in (await self.config.all_guilds()).items():
            enabled = data.get("mcp_enabled_servers", [])
            if name in enabled:
                await self.config.guild_from_id(guild_id).mcp_enabled_servers.set(
                    [server_alias for server_alias in enabled if server_alias != name]
                )
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
        bearer_token = (await self.bot.get_shared_api_tokens(f"mcp_{name}")).get(
            "token"
        )
        oauth = await self.services.mcp.oauth.load(name)
        oauth_configured = (
            bool(oauth.get("token")) and oauth.get("url") == server["url"]
        )
        enabled = name in await self.config.guild(ctx.guild).mcp_enabled_servers()
        auth_method = (
            "OAuth"
            if oauth_configured
            else "Bearer token"
            if bearer_token
            else "no authentication"
        )
        connection_detail = ""
        next_step = ""
        try:
            tools = await self.services.mcp.tools_for_mcp_server(
                ctx.guild.id, name, server, refresh=True
            )
            connection = "Connected"
        except MCPOAuthRequired:
            tools = []
            connection = "Sign-in required"
            auth_method = "OAuth"
            next_step = "Remove and add this server again to authenticate."
        except MCPAuthError as exc:
            tools = []
            connection = "Authentication rejected"
            connection_detail = str(exc)[:1000]
        except MCPError as exc:
            tools = []
            connection = "Connection failed"
            connection_detail = str(exc)[:1000]
            next_step = f"`{ctx.clean_prefix}aiuser tools mcp info {name}`"
        embed = discord.Embed(
            title=f"MCP server: {name}",
            color=await ctx.embed_color(),
        )
        embed.add_field(name="Enabled", value="✅" if enabled else "❌", inline=True)
        embed.add_field(
            name="Connection",
            value=(
                f"🟢 Via {auth_method}"
                if connection == "Connected"
                else f"🔴 {connection}"
            ),
            inline=True,
        )
        if connection_detail:
            embed.add_field(name="Details", value=connection_detail, inline=False)
        if next_step:
            embed.add_field(
                name="Next step",
                value=next_step,
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
        """Enable an MCP server for this Discord server."""
        servers = await self.config.mcp_servers()
        if name not in servers:
            return await ctx.send(f"Unknown MCP server `{name}`.")
        enabled = await self.config.guild(ctx.guild).mcp_enabled_servers()
        if name not in enabled:
            enabled.append(name)
            await self.config.guild(ctx.guild).mcp_enabled_servers.set(enabled)
        await self.config.guild(ctx.guild).function_calling.set(True)
        embed = discord.Embed(
            title="MCP server enabled",
            description=f"`{name}` is enabled for this Discord server.",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @mcp.command(name="disable")
    async def mcp_disable(self, ctx: commands.Context, name: str):
        """Disable an MCP server for this Discord server."""
        if name not in await self.config.mcp_servers():
            return await ctx.send(f"Unknown MCP server `{name}`.")
        enabled = await self.config.guild(ctx.guild).mcp_enabled_servers()
        if name in enabled:
            await self.config.guild(ctx.guild).mcp_enabled_servers.set(
                [server_alias for server_alias in enabled if server_alias != name]
            )
        await self.services.mcp.invalidate(ctx.guild.id, name)
        embed = discord.Embed(
            title=f"{name} MCP server is now:",
            description="Disabled",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
