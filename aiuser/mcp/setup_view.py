from __future__ import annotations

from urllib.parse import urlsplit

import discord

from .access_view import MCPAccessView, access_audience, describe_access
from .client import MCPAuthError, MCPError, MCPOAuthRequired
from .view import MCPAuthView


class MCPPicker(discord.ui.Select):
    def __init__(self, label, names, page, callback, selected=None):
        start = page * 25
        options = [
            discord.SelectOption(
                label=name[:100], value=str(index), default=name == selected
            )
            for index, name in enumerate(names[start : start + 25], start)
        ]
        super().__init__(placeholder=label, options=options, row=0)
        self.names = names
        self.choose = callback

    async def callback(self, interaction):
        await self.choose(interaction, self.names[int(self.values[0])])


def update_pagination(view, count, page):
    for button, disabled in (
        (view.previous, page == 0),
        (view.next_page, (page + 1) * 25 >= count),
    ):
        if count <= 25:
            view.remove_item(button)
        else:
            if button not in view.children:
                view.add_item(button)
            button.disabled = disabled


class MCPSetupView(discord.ui.View):
    def __init__(self, manager, guild, owner_id):
        super().__init__(timeout=600)
        self.manager = manager
        self.guild = guild
        self.owner_id = owner_id
        self.alias = None
        self.page = 0
        self.picker = None
        self.connection = {}

    async def interaction_check(self, interaction):
        if (
            interaction.user.id == self.owner_id
            and interaction.guild_id == self.guild.id
            and await self.manager.bot.is_owner(interaction.user)
        ):
            return True
        await interaction.response.send_message(
            "Only the bot owner who opened this panel can use it.", ephemeral=True
        )
        return False

    async def embed(self):
        servers = await self.manager.config.mcp_servers()
        names = sorted(servers)
        self.page = min(self.page, max(0, (len(names) - 1) // 25))
        if self.picker:
            self.remove_item(self.picker)
            self.picker = None
        if names:
            self.picker = MCPPicker(
                "Choose an MCP server", names, self.page, self.select, self.alias
            )
            self.add_item(self.picker)
        update_pagination(self, len(names), self.page)
        server = servers.get(self.alias)
        for control in (self.primary, self.tool_access, self.actions):
            if server is None:
                self.remove_item(control)
            elif control not in self.children:
                self.add_item(control)
        self.remove_item(self.add)
        self.add_item(self.add)
        embed = discord.Embed(title="MCP setup", color=discord.Color.blurple())
        embed.set_footer(
            text="Bot-wide: URL and sign-in · This Discord server: enablement and tool access"
        )
        self.add.style = (
            discord.ButtonStyle.primary
            if server is None
            else discord.ButtonStyle.secondary
        )
        if server is None:
            embed.description = (
                "Choose an MCP server or add a new one."
                if names
                else "Add an MCP server to get started."
            )
        else:
            guild = self.manager.config.guild(self.guild)
            enabled = self.alias in await guild.mcp_enabled_servers()
            connection, status = self.connection.get(
                (self.alias, server["url"]), ("unchecked", "Not checked yet")
            )
            self.primary.label = (
                ("Disable here" if enabled else "Review and enable")
                if connection == "connected"
                else "Sign in"
                if connection == "auth"
                else "Check connection"
            )
            self.actions.options = [
                discord.SelectOption(label="Edit URL", value="url"),
                discord.SelectOption(label="Remove bot-wide", value="remove"),
            ]
            if connection == "connected":
                self.actions.options.insert(
                    0, discord.SelectOption(label="Check connection", value="check")
                )
            elif enabled:
                self.actions.options.insert(
                    0, discord.SelectOption(label="Disable here", value="disable")
                )
            rules = (await guild.mcp_tool_access()).get(self.alias, {})
            overrides = len(rules.get("tools", {}))
            embed.description = f"**{self.alias}** · {'Enabled' if enabled else 'Disabled'} in this Discord server"
            embed.add_field(name="Connection", value=status, inline=False)
            embed.add_field(
                name="Who can use tools here",
                value=f"{describe_access(rules.get('default'))} by default · {overrides} tool {'override' if overrides == 1 else 'overrides'}",
                inline=False,
            )
            url = server["url"][:900].replace("`", r"\`")
            embed.add_field(name="MCP endpoint", value=f"`{url}`", inline=False)
        return embed

    async def refresh(self, interaction):
        await interaction.edit_original_response(embed=await self.embed(), view=self)

    async def select(self, interaction, name):
        await interaction.response.defer()
        self.alias = name
        await self.refresh(interaction)

    @discord.ui.button(label="Previous", row=1)
    async def previous(self, interaction, _button):
        await interaction.response.defer()
        self.page -= 1
        await self.refresh(interaction)

    @discord.ui.button(label="Next", row=1)
    async def next_page(self, interaction, _button):
        await interaction.response.defer()
        self.page += 1
        await self.refresh(interaction)

    @discord.ui.button(label="Add MCP server", style=discord.ButtonStyle.primary, row=2)
    async def add(self, interaction, _button):
        await interaction.response.send_modal(MCPServerModal(self))

    @discord.ui.select(placeholder="More actions", row=3)
    async def actions(self, interaction, select):
        actions = {
            "disable": self.disable,
            "check": self.auth,
            "url": self.url,
            "remove": self.remove,
        }
        await actions[select.values[0]](interaction)

    async def url(self, interaction):
        alias = self.alias
        server = (await self.manager.config.mcp_servers()).get(alias)
        if server is None:
            return await interaction.response.send_message(
                "This server was removed.", ephemeral=True
            )
        await interaction.response.send_modal(
            MCPServerModal(self, alias, server["url"])
        )

    @discord.ui.button(
        label="Check connection", style=discord.ButtonStyle.primary, row=2
    )
    async def primary(self, interaction, _button):
        if self.primary.label == "Review and enable":
            await self.review_enable(interaction)
        elif self.primary.label == "Disable here":
            await self.disable(interaction)
        else:
            await self.auth(interaction)

    async def review_enable(self, interaction):
        alias = self.alias
        await interaction.response.defer()
        server = (await self.manager.config.mcp_servers()).get(alias)
        if server is None:
            return await self.refresh(interaction)
        try:
            tools = await self.manager.tools_for_mcp_server(
                self.guild.id, alias, server
            )
        except MCPError:
            return await self.check_connection(interaction, alias, server)
        review = MCPEnableReview(
            self, alias, server["url"], sorted({tool.native_name for tool in tools})
        )
        await interaction.edit_original_response(
            embed=await review.embed(), view=review
        )

    async def disable(self, interaction):
        await self.toggle(interaction, False)

    async def toggle(self, interaction, enabled):
        alias = self.alias
        await interaction.response.defer()
        try:
            await self.manager.set_enabled(self.guild.id, alias, enabled)
        except MCPError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        await self.refresh(interaction)

    async def auth(self, interaction):
        alias = self.alias
        await interaction.response.defer()
        server = (await self.manager.config.mcp_servers()).get(alias)
        if server is None:
            return await self.refresh(interaction)
        await self.check_connection(interaction, alias, server)

    async def check_connection(self, interaction, alias, server, *, show_auth=True):
        key = (alias, server["url"])
        challenge = ""
        oauth_available = True
        try:
            tools = await self.manager.tools_for_mcp_server(
                self.guild.id, alias, server, refresh=True
            )
            self.connection[key] = (
                "connected",
                f"Connected · {len(tools)} {'tool' if len(tools) == 1 else 'tools'}",
            )
        except MCPOAuthRequired as exc:
            challenge = exc.challenge
            self.connection[key] = ("auth", "Sign-in required")
        except MCPAuthError:
            oauth_available = False
            self.connection[key] = (
                "auth",
                "Sign-in required or saved credentials rejected",
            )
        except MCPError as exc:
            self.connection[key] = ("error", str(exc)[:250])
        await self.refresh(interaction)
        if not show_auth or self.connection[key][0] != "auth":
            return

        async def connected(tool_count):
            self.connection[key] = (
                "connected",
                f"Connected · {tool_count} {'tool' if tool_count == 1 else 'tools'}",
            )
            await self.refresh(interaction)

        view = MCPAuthView(
            self.manager,
            alias,
            self.owner_id,
            self.guild.id,
            server["url"],
            challenge,
            oauth_available,
        )
        view.on_connected = connected
        view.message = await interaction.followup.send(
            embed=discord.Embed(
                title=f"Sign in to {alias}",
                description="Credentials are shared by every Discord server using this connection.",
            ),
            view=view,
            ephemeral=True,
            wait=True,
        )

    @discord.ui.button(label="Tool access", row=2)
    async def tool_access(self, interaction, _button):
        await self.access(interaction)

    async def access(self, interaction):
        alias = self.alias
        await interaction.response.defer()
        server = (await self.manager.config.mcp_servers()).get(alias)
        if server is None:
            return await interaction.followup.send(
                "This server was removed.", ephemeral=True
            )
        rules = await self.manager.config.guild(self.guild).mcp_tool_access()
        names = set(rules.get(alias, {}).get("tools", {}))
        warning = ""
        try:
            tools = await self.manager.tools_for_mcp_server(
                self.guild.id, alias, server
            )
            names.update(tool.native_name for tool in tools)
        except MCPError:
            warning = "\nThe tool catalog is unavailable. The server default and saved rules can still be edited."
        picker = MCPToolPicker(self, alias, server["url"], sorted(names))
        await picker.open_rule(interaction, None, warning=warning, deferred=True)

    async def remove(self, interaction):
        await interaction.response.send_modal(MCPRemoveModal(self, self.alias))


class MCPEnableReview(discord.ui.View):
    def __init__(self, setup, alias, url, tools):
        super().__init__(timeout=300)
        self.setup = setup
        self.alias = alias
        self.url = url
        self.tools = tools
        self.rules = {}

    async def interaction_check(self, interaction):
        return await self.setup.interaction_check(interaction)

    async def read_rules(self):
        config = self.setup.manager.config.guild(self.setup.guild)
        return (await config.mcp_tool_access()).get(self.alias, {})

    async def embed(self):
        self.rules = await self.read_rules()
        default = describe_access(self.rules.get("default"))
        overrides = self.rules.get("tools", {})
        shown = [
            f"`{name[:50].replace(chr(96), chr(39))}` · {access_audience(overrides.get(name, self.rules.get('default')), limit=2)}"
            for name in self.tools[:8]
        ]
        if len(self.tools) > 8:
            shown.append(
                f"… and {len(self.tools) - 8} more. Open Tool access for the full list."
            )
        embed = discord.Embed(
            title="Review before enabling", color=discord.Color.blurple()
        )
        embed.description = (
            f"`{self.alias}` in **{discord.utils.escape_markdown(self.setup.guild.name)}**"
            f"\n**Default access:** {default}"
        )
        embed.add_field(
            name="Tools and access",
            value="\n".join(shown) or "No tools found.",
            inline=False,
        )
        if default == "Everyone" or any(
            rule["everyone"] for rule in overrides.values()
        ):
            embed.set_footer(
                text="Anyone who can chat with the bot can use tools marked Everyone."
            )
        return embed

    @discord.ui.button(label="Enable here", style=discord.ButtonStyle.primary)
    async def enable(self, interaction, _button):
        await interaction.response.defer()
        server = (await self.setup.manager.config.mcp_servers()).get(self.alias)
        if server is None or server["url"] != self.url:
            await self.setup.refresh(interaction)
            return await interaction.followup.send(
                "The endpoint changed. Check the connection again.", ephemeral=True
            )
        if self.rules != await self.read_rules():
            await interaction.edit_original_response(
                embed=await self.embed(), view=self
            )
            return await interaction.followup.send(
                "Access changed. Review the updated rules before enabling.",
                ephemeral=True,
            )
        try:
            await self.setup.manager.set_enabled(self.setup.guild.id, self.alias, True)
        except MCPError as exc:
            return await interaction.followup.send(str(exc), ephemeral=True)
        await self.setup.refresh(interaction)

    @discord.ui.button(label="Edit tool access")
    async def access(self, interaction, _button):
        self.setup.alias = self.alias
        await self.setup.access(interaction)

    @discord.ui.button(label="Back")
    async def back(self, interaction, _button):
        await interaction.response.defer()
        await self.setup.refresh(interaction)


class MCPToolPicker(discord.ui.View):
    def __init__(self, setup, alias, url, names):
        super().__init__(timeout=300)
        self.setup = setup
        self.alias = alias
        self.url = url
        self.names = names
        self.page = 0
        self.picker = None
        self.update_picker()

    async def interaction_check(self, interaction):
        return await self.setup.interaction_check(interaction)

    def update_picker(self):
        if self.picker:
            self.remove_item(self.picker)
        if self.names:
            self.picker = MCPPicker(
                "Choose a tool", self.names, self.page, self.open_rule
            )
            self.add_item(self.picker)
        update_pagination(self, len(self.names), self.page)

    async def show_tools(self, interaction):
        await interaction.response.edit_message(
            embed=discord.Embed(title=f"Tool overrides for {self.alias}"), view=self
        )

    async def open_rule(self, interaction, tool, *, warning="", deferred=False):
        view = MCPAccessView(
            self.setup.manager,
            self.setup.guild,
            self.setup.owner_id,
            self.alias,
            self.url,
            tool,
        )
        if self.names:
            view.add_item(discord.ui.Button(label="Choose a tool", row=3))
            view.children[-1].callback = self.show_tools
        view.add_item(discord.ui.Button(label="Back to setup", row=3))

        async def back(back_interaction):
            await back_interaction.response.defer()
            await self.setup.refresh(back_interaction)

        view.children[-1].callback = back
        embed = await view.embed()
        if warning:
            embed.set_footer(text=warning.strip())
        edit = (
            interaction.edit_original_response
            if deferred
            else interaction.response.edit_message
        )
        await edit(embed=embed, view=view)

    @discord.ui.button(label="Default access", row=1)
    async def default(self, interaction, _button):
        await self.open_rule(interaction, None)

    @discord.ui.button(label="Previous", row=1)
    async def previous(self, interaction, _button):
        self.page = max(0, self.page - 1)
        self.update_picker()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Next", row=1)
    async def next_page(self, interaction, _button):
        self.page = min(self.page + 1, max(0, (len(self.names) - 1) // 25))
        self.update_picker()
        await interaction.response.edit_message(view=self)


class MCPServerModal(discord.ui.Modal, title="MCP server"):
    alias_input = discord.ui.TextInput(
        label="MCP server name", placeholder="e.g. team-docs", max_length=32
    )
    endpoint = discord.ui.TextInput(
        label="MCP endpoint URL",
        placeholder="https://example.com/mcp",
        max_length=4000,
    )

    def __init__(self, setup, alias=None, url=None):
        super().__init__(
            title="Edit MCP server URL" if alias else "Add MCP server", timeout=300
        )
        self.setup = setup
        self.alias = alias
        if alias:
            self.remove_item(self.alias_input)
            self.endpoint.default = url

    async def interaction_check(self, interaction):
        return await self.setup.interaction_check(interaction)

    async def on_submit(self, interaction):
        await interaction.response.defer()
        name = self.alias or self.alias_input.value.strip()
        url = self.endpoint.value.strip()
        try:
            endpoint = urlsplit(url)
            if endpoint.scheme not in {"http", "https"} or not endpoint.hostname:
                raise ValueError
        except ValueError:
            return await interaction.followup.send(
                "Enter a valid HTTP or HTTPS endpoint URL.", ephemeral=True
            )
        try:
            if self.alias:
                await self.setup.manager.update_url(name, url)
            else:
                await self.setup.manager.add_server(name, url)
        except MCPError as exc:
            return await interaction.followup.send(str(exc), ephemeral=True)
        self.setup.alias = name
        await self.setup.check_connection(
            interaction, name, {"url": url}, show_auth=False
        )


class MCPRemoveModal(discord.ui.Modal, title="Remove MCP server bot-wide"):
    confirmation = discord.ui.TextInput(
        label="Type the server name to remove it", max_length=32
    )

    def __init__(self, setup, alias):
        super().__init__(timeout=300)
        self.setup = setup
        self.alias = alias
        self.confirmation.placeholder = alias

    async def interaction_check(self, interaction):
        return await self.setup.interaction_check(interaction)

    async def on_submit(self, interaction):
        if self.confirmation.value.strip() != self.alias:
            return await interaction.response.send_message(
                "The server name did not match.", ephemeral=True
            )
        await interaction.response.defer()
        try:
            await self.setup.manager.remove_server(self.alias)
        except MCPError as exc:
            return await interaction.followup.send(str(exc), ephemeral=True)
        if self.setup.alias == self.alias:
            self.setup.alias = None
        await self.setup.refresh(interaction)
