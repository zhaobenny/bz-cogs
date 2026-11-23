from __future__ import annotations

from typing import Optional

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import SimpleMenu

from aiuser.mcp.access_view import MCPAccessView, MCPPanelLauncher
from aiuser.mcp.client import MCPAuthError, MCPError, MCPOAuthRequired
from aiuser.mcp.setup_view import MCPSetupView
from aiuser.mcp.view import MCPAuthView
from aiuser.settings.functions.utilities import functions
from aiuser.types.abc import MixinMeta


class MCPSettings(MixinMeta):
    @functions.group(name="mcp", invoke_without_command=True)
    async def mcp(self, ctx: commands.Context):
        """Configure remote MCP tool servers."""
        if self.services is None or self.services.mcp is None:
            return await ctx.send("MCP is still loading. Try again shortly.")
        panel = MCPSetupView(self.services.mcp, ctx.guild, ctx.author.id)
        await ctx.send(
            "Open the private panel to manage MCP connections and tool access.",
            view=MCPPanelLauncher(panel, "Open MCP setup"),
        )

    @mcp.command(name="servers", aliases=["list"])
    async def mcp_servers(self, ctx: commands.Context):
        """List configured MCP servers and if they are currently enabled for the current Discord server."""
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
        """Add an MCP server to the catalog of available servers to use."""
        try:
            server = await self.services.mcp.add_server(name, url)
        except MCPError as exc:
            return await ctx.send(str(exc))
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
                ctx.guild.id, name, server, refresh=True
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
        except MCPAuthError as exc:
            embed.add_field(
                name="Connection",
                value=f"{exc}\nSet a Bearer token below to authenticate this server.",
                inline=False,
            )
            view = MCPAuthView(
                self.services.mcp,
                name,
                ctx.author.id,
                ctx.guild.id,
                url,
                None,
                oauth_available=False,
            )
            view.message = await ctx.send(embed=embed, view=view)
            return
        except MCPError as exc:
            embed.add_field(
                name="Connection",
                value=f"{exc}\nOpen Connection & sign-in in MCP setup to retry.",
                inline=False,
            )
        await ctx.send(embed=embed)

    @mcp.command(name="url")
    async def mcp_url(self, ctx: commands.Context, name: str, url: str):
        """Reconfigure the URL a MCP server uses."""
        try:
            server = await self.services.mcp.update_url(name, url)
        except MCPError as exc:
            return await ctx.send(str(exc))
        embed = discord.Embed(
            title="MCP server URL updated",
            description=f"`{name}`",
            color=await ctx.embed_color(),
        )
        embed.add_field(name="URL", value=f"`{url}`", inline=False)
        try:
            await self.services.mcp.tools_for_mcp_server(
                ctx.guild.id, name, server, refresh=True
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
        except MCPAuthError as exc:
            embed.add_field(
                name="Connection",
                value=f"{exc}\nSet a Bearer token below to authenticate this server.",
                inline=False,
            )
            view = MCPAuthView(
                self.services.mcp,
                name,
                ctx.author.id,
                ctx.guild.id,
                url,
                None,
                oauth_available=False,
            )
            view.message = await ctx.send(embed=embed, view=view)
            return
        except MCPError as exc:
            embed.add_field(name="Connection", value=str(exc), inline=False)
        await ctx.send(embed=embed)

    @mcp.command(name="remove", aliases=["delete"])
    async def mcp_remove(self, ctx: commands.Context, name: str):
        """Remove an MCP server by name from the available catalog."""
        try:
            await self.services.mcp.remove_server(name)
        except MCPError as exc:
            return await ctx.send(str(exc))
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
            next_step = f"Open `{ctx.clean_prefix}aiuser tools mcp`, then choose Connection & sign-in."
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
            value=("🟢 Connected" if connection == "Connected" else f"🔴 {connection}"),
            inline=True,
        )
        embed.add_field(name="Authentication", value=auth_method, inline=True)
        if connection_detail:
            embed.add_field(name="Details", value=connection_detail, inline=False)
        if next_step:
            embed.set_footer(text=f"Troubleshooting: {next_step}")
        embed.add_field(name="URL", value=f"`{server['url']}`", inline=False)
        if tools:
            names = "\n".join(sorted(tool.native_name for tool in tools))
            pages = []
            for page in pagify(names, page_length=950, shorten_by=10):
                pages.append(
                    embed.copy().add_field(
                        name=f"Tools ({len(tools)})", value=box(page), inline=False
                    )
                )
            if len(pages) > 1:
                return await SimpleMenu(pages).start(ctx)
            if pages:
                embed = pages[0]
        elif connection == "Connected":
            embed.add_field(name="Tools", value="None", inline=False)
        await ctx.send(embed=embed)

    @mcp.command(name="enable")
    async def mcp_enable(self, ctx: commands.Context, name: str):
        """Enable an MCP server. Use the access command to manage who can use its tools."""
        try:
            await self.services.mcp.set_enabled(ctx.guild.id, name, True)
        except MCPError as exc:
            return await ctx.send(str(exc))
        embed = discord.Embed(
            title="MCP server enabled",
            description=f"`{name}` is enabled for this Discord server.",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @mcp.command(name="access")
    @checks.is_owner()
    async def mcp_access(
        self,
        ctx: commands.Context,
        name: str,
        *,
        tool: Optional[str] = None,  # noqa: UP045 - Red evaluates converters on Python 3.9
    ):
        """Manage the server default or a named tool's access for this Discord server."""
        if self.services is None or self.services.mcp is None:
            return await ctx.send("MCP is still loading. Try again shortly.")
        server = (await self.config.mcp_servers()).get(name)
        if server is None:
            return await ctx.send(f"Unknown MCP server `{name}`.")
        if tool is not None:
            access = await self.config.guild(ctx.guild).mcp_tool_access()
            if tool not in access.get(name, {}).get("tools", {}):
                try:
                    async with ctx.typing():
                        tools = await self.services.mcp.tools_for_mcp_server(
                            ctx.guild.id, name, server
                        )
                except MCPError as exc:
                    return await ctx.send(str(exc))
                if all(tool != entry.native_name for entry in tools):
                    return await ctx.send(
                        f"Unknown tool. Run `{ctx.clean_prefix}aiuser tools mcp info {name}` "
                        "to see its tool names."
                    )
        panel = MCPAccessView(
            self.services.mcp, ctx.guild, ctx.author.id, name, server["url"], tool
        )
        await ctx.send(
            "Open the private panel to edit this Discord server’s MCP tool access.",
            view=MCPPanelLauncher(panel),
        )

    @mcp.command(name="disable")
    async def mcp_disable(self, ctx: commands.Context, name: str):
        """Disable an MCP server for this Discord server."""
        try:
            await self.services.mcp.set_enabled(ctx.guild.id, name, False)
        except MCPError as exc:
            return await ctx.send(str(exc))
        embed = discord.Embed(
            title=f"{name} MCP server is now:",
            description="Disabled",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
