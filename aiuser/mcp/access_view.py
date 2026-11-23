from __future__ import annotations

import discord
from redbot.core.utils.chat_formatting import escape

from .access import AccessRule, access_rule


def describe_access(rule):
    if rule is None or rule["everyone"]:
        return "Everyone"
    members, roles = len(rule["members"]), len(rule["roles"])
    counts = []
    if members:
        counts.append(f"{members} {'member' if members == 1 else 'members'}")
    if roles:
        counts.append(f"{roles} {'role' if roles == 1 else 'roles'}")
    return " and ".join(counts) or "No one"


def access_audience(rule, limit=12):
    if rule is None or rule["everyone"]:
        return "Everyone"
    entries = [f"<@{value}>" for value in rule["members"]]
    entries.extend(f"<@&{value}>" for value in rule["roles"])
    if len(entries) > limit:
        return " ".join(entries[:limit]) + f" + {len(entries) - limit} more"
    return " ".join(entries) or "No one"


class MCPAccessView(discord.ui.View):
    def __init__(self, manager, guild, owner_id, alias, url, tool):
        super().__init__(timeout=300)
        self.manager = manager
        self.guild = guild
        self.owner_id = owner_id
        self.alias = alias
        self.url = url
        self.tool = tool
        self.access = manager.config.guild(guild).mcp_tool_access
        self.has_draft = False
        self.draft: AccessRule | None = None
        self._picking_people = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
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

    async def embed(self) -> discord.Embed:
        server = (await self.access()).get(self.alias, {})
        default = server.get("default", access_rule(everyone=True))
        rule = (
            server.get("tools", {}).get(self.tool) if self.tool is not None else default
        )
        saved = rule
        if self.has_draft:
            rule = self.draft
        if self.has_draft and self._picking_people:
            mode = "specific"
        elif rule is None:
            mode = "inherit"
        elif rule["everyone"]:
            mode = "everyone"
        else:
            mode = "specific" if rule["members"] or rule["roles"] else "nobody"
        show_people = mode == "specific"
        options = [
            ("Everyone", "everyone"),
            ("Selected members or roles", "specific"),
            ("No one", "nobody"),
        ]
        if self.tool is not None:
            options.append(("Use default access", "inherit"))
        self.audience.options = [
            discord.SelectOption(label=label, value=value, default=value == mode)
            for label, value in options
        ]
        for button in (self.apply, self.discard):
            if not self.has_draft:
                self.remove_item(button)
            elif button not in self.children:
                self.add_item(button)
        self.apply.disabled = self.draft == saved or (
            show_people and self.draft == access_rule()
        )
        rule = default if rule is None else rule
        for picker, ids, kind in (
            (self.members, rule["members"], "user"),
            (self.roles, rule["roles"], "role"),
        ):
            if not show_people:
                self.remove_item(picker)
                continue
            if picker not in self.children:
                self.add_item(picker)
            if hasattr(picker, "default_values"):
                picker.default_values = [
                    discord.SelectDefaultValue(
                        id=value, type=discord.SelectDefaultValueType[kind]
                    )
                    for value in ids
                ]
        title = (
            "Default tool access"
            if self.tool is None
            else escape(self.tool[:250], formatting=True, mass_mentions=True)
        )
        current = access_audience(default if saved is None else saved)
        if saved is None:
            current = f"{current} · uses default access"
        embed = discord.Embed(
            title=title,
            description=f"`{self.alias}` in **{escape(self.guild.name, formatting=True, mass_mentions=True)}**",
            color=discord.Color.orange() if self.has_draft else discord.Color.blurple(),
        )
        if self.has_draft:
            proposed = access_audience(rule)
            if show_people and proposed == "No one":
                proposed = "Choose at least one member or role."
            elif mode == "inherit":
                proposed = f"{proposed} · uses default access"
            embed.add_field(name="Unsaved access", value=proposed, inline=False)
        embed.add_field(name="Current access", value=current, inline=False)
        return embed

    async def _save(self, interaction: discord.Interaction, rule: AccessRule | None):
        await interaction.response.defer()
        async with self.manager.config.mcp_servers.get_lock():
            server = (await self.manager.config.mcp_servers()).get(self.alias)
            current = server is not None and server["url"] == self.url
            if current:
                async with self.access() as servers:
                    access = servers.setdefault(self.alias, {})
                    rules, key = (
                        (access, "default")
                        if self.tool is None
                        else (access.setdefault("tools", {}), self.tool)
                    )
                    if rule is None:
                        rules.pop(key, None)
                    else:
                        rules[key] = rule
        if not current:
            self.stop()
            return await interaction.edit_original_response(
                content="This MCP server changed. Open the access panel again.",
                embed=None,
                view=None,
            )
        self.has_draft = False
        self.draft = None
        self._picking_people = False
        await interaction.edit_original_response(embed=await self.embed(), view=self)

    @discord.ui.select(placeholder="Who can use this?", row=0)
    async def audience(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        mode = select.values[0]
        self.has_draft = True
        self._picking_people = mode == "specific"
        if mode == "specific":
            if self.draft is None or self.draft["everyone"]:
                rules = (await self.access()).get(self.alias, {})
                default = rules.get("default", access_rule())
                current = rules.get("tools", {}).get(self.tool, default)
                self.draft = {**current, "everyone": False}
        else:
            self.draft = (
                None if mode == "inherit" else access_rule(everyone=mode == "everyone")
            )
        await self.refresh_draft(interaction)

    async def refresh_draft(self, interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(embed=await self.embed(), view=self)

    @discord.ui.button(label="Save access", style=discord.ButtonStyle.primary, row=3)
    async def apply(self, interaction, _button):
        if not self.has_draft or (self._picking_people and self.draft == access_rule()):
            return await interaction.response.defer()
        await self._save(interaction, self.draft)

    @discord.ui.button(label="Discard changes", row=3)
    async def discard(self, interaction, _button):
        self.has_draft = False
        self.draft = None
        self._picking_people = False
        await self.refresh_draft(interaction)

    async def saved_access(self):
        rules = (await self.access()).get(self.alias, {})
        default = rules.get("default", access_rule(everyone=True))
        rule = (
            default
            if self.tool is None
            else rules.get("tools", {}).get(self.tool, default)
        )
        return {**rule, "everyone": False}

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Allowed members",
        min_values=0,
        max_values=25,
        row=1,
    )
    async def members(
        self, interaction: discord.Interaction, select: discord.ui.UserSelect
    ):
        self.has_draft = True
        self._picking_people = True
        self.draft = {
            **(self.draft or await self.saved_access()),
            "members": [member.id for member in select.values],
        }
        await self.refresh_draft(interaction)

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Allowed roles",
        min_values=0,
        max_values=25,
        row=2,
    )
    async def roles(
        self, interaction: discord.Interaction, select: discord.ui.RoleSelect
    ):
        self.has_draft = True
        self._picking_people = True
        self.draft = {
            **(self.draft or await self.saved_access()),
            "roles": [role.id for role in select.values],
        }
        await self.refresh_draft(interaction)


class MCPPanelLauncher(discord.ui.View):
    def __init__(self, panel, label="Open access settings"):
        super().__init__(timeout=300)
        self.panel = panel
        self.open_panel.label = label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.panel.interaction_check(interaction)

    @discord.ui.button(label="Open access settings", style=discord.ButtonStyle.primary)
    async def open_panel(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        await interaction.response.send_message(
            embed=await self.panel.embed(), view=self.panel, ephemeral=True
        )
        self.stop()
        if interaction.message:
            try:
                await interaction.message.edit(
                    content="MCP panel opened privately.", view=None
                )
            except discord.HTTPException:
                pass
