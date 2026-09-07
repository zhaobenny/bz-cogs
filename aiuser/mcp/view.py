from __future__ import annotations

import logging

import discord

from .client import MCPError
from .oauth import LOGIN_SECONDS

logger = logging.getLogger("red.bz_cogs.aiuser.mcp")


class MCPTokenModal(discord.ui.Modal, title="Set MCP Bearer token"):
    token = discord.ui.TextInput(
        label="Bearer token",
        max_length=4000,
        placeholder="Paste the token here",
    )

    def __init__(self, manager, alias, owner_id, guild_id, auth_view):
        super().__init__(timeout=LOGIN_SECONDS)
        self.manager = manager
        self.alias = alias
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.auth_view = auth_view

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != self.owner_id or not await self.manager.bot.is_owner(
            interaction.user
        ):
            return await interaction.followup.send(
                "This authentication belongs to another owner.", ephemeral=True
            )

        service = f"mcp_{self.alias}"
        old_token = (await self.manager.bot.get_shared_api_tokens(service)).get("token")
        await self.manager.bot.set_shared_api_tokens(service, token=self.token.value)
        await self.manager.invalidate_server(self.alias)
        try:
            server = (await self.manager.config.mcp_servers()).get(self.alias)
            if not server:
                raise MCPError("The server was removed.")
            tools = await self.manager.tools_for_mcp_server(
                self.guild_id, self.alias, server, refresh=True
            )
        except Exception as exc:
            if old_token:
                await self.manager.bot.set_shared_api_tokens(service, token=old_token)
            else:
                await self.manager.bot.remove_shared_api_tokens(service, "token")
            await self.manager.invalidate_server(self.alias)
            logger.warning(
                "MCP onboarding failed for %s (%s)", self.alias, type(exc).__name__
            )
            await self.auth_view.finish(False)
            return await interaction.followup.send(
                embed=discord.Embed(
                    title="MCP authentication failed",
                    description="That token could not authenticate the MCP server.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )

        await self.auth_view.finish(True)
        await interaction.followup.send(
            embed=discord.Embed(
                title="MCP authentication configured",
                description=f"`{self.alias}` is ready with {len(tools)} tools. Enable it for a Discord server when ready.",
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )

    async def on_error(self, interaction, error):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Authentication failed. Remove and add the server again to retry.",
                ephemeral=True,
            )


class MCPAuthView(discord.ui.View):
    def __init__(self, manager, alias, owner_id, guild_id, url, challenge):
        super().__init__(timeout=LOGIN_SECONDS)
        self.manager = manager
        self.alias = alias
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.url = url
        self.challenge = challenge
        self.message = None
        self.completed = False

    async def interaction_check(self, interaction):
        if interaction.user.id == self.owner_id and await self.manager.bot.is_owner(
            interaction.user
        ):
            return True
        await interaction.response.send_message(
            embed=discord.Embed(
                title="MCP authentication denied",
                description="Only the owner who started this authentication can use it.",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="OAuth sign in", style=discord.ButtonStyle.primary)
    async def oauth(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        try:
            link, state = await self.manager.oauth.begin(
                self.alias,
                self.url,
                self.challenge,
                self.owner_id,
                self.guild_id,
            )
            view = MCPLoginView(
                self.manager, self.alias, self.owner_id, link, state, self
            )
            view.message = await interaction.followup.send(
                embed=discord.Embed(
                    title=f"Sign in to MCP server: {self.alias}",
                    description=(
                        "The final localhost page **will fail** to load. Copy its full URL from the address bar, "
                        "then use **Paste URL** here.\n"
                    ),
                    color=discord.Color.blurple(),
                ).set_footer(
                    text="The authorized account will be used for all servers MCP requests."
                ),
                view=view,
                ephemeral=True,
                wait=True,
            )
        except MCPError as exc:
            logger.warning(
                "MCP onboarding failed for %s (%s)", self.alias, type(exc).__name__
            )
            await self.finish(False)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Could not start OAuth sign-in",
                    description=str(exc),
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
        except Exception as exc:
            logger.warning(
                "MCP onboarding failed for %s (%s)", self.alias, type(exc).__name__
            )
            await self.finish(False)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Could not start OAuth sign-in",
                    description="Remove and add the server again to retry.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )

    @discord.ui.button(label="Set Bearer token", style=discord.ButtonStyle.secondary)
    async def token(self, interaction, button):
        await interaction.response.send_modal(
            MCPTokenModal(self.manager, self.alias, self.owner_id, self.guild_id, self)
        )

    async def finish(self, success):
        if self.completed:
            return
        self.completed = True
        self.stop()
        if not self.message:
            return
        try:
            await self.message.edit(
                embed=discord.Embed(
                    title=(
                        "MCP onboarding succeeded"
                        if success
                        else "MCP onboarding failed"
                    ),
                    description=(
                        f"`{self.alias}` authentication is configured."
                        if success
                        else "Authentication failed. Check the logs for details."
                    ),
                    color=(discord.Color.green() if success else discord.Color.red()),
                ),
                content=None,
                view=None,
            )
        except discord.HTTPException:
            pass

    async def on_timeout(self):
        if self.completed:
            return
        if self.message:
            try:
                await self.message.edit(
                    embed=discord.Embed(
                        title="MCP authentication expired",
                        description="Remove and add the server again.",
                        color=discord.Color.orange(),
                    ),
                    content=None,
                    view=None,
                )
            except discord.HTTPException:
                pass

    async def on_error(self, interaction, error, item):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="MCP authentication failed",
                    description="Remove and add the server again to retry.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )


class MCPCallbackModal(discord.ui.Modal, title="Finish MCP sign-in"):
    callback_url = discord.ui.TextInput(
        label="Full localhost callback URL",
        max_length=4000,
        placeholder="http://localhost:8765/callback?code=...&state=...",
    )

    def __init__(self, view):
        super().__init__(timeout=LOGIN_SECONDS)
        self.login = view

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        view = self.login
        if interaction.user.id != view.owner_id or not await view.manager.bot.is_owner(
            interaction.user
        ):
            return await interaction.followup.send(
                embed=discord.Embed(
                    title="MCP sign-in denied",
                    description="This login belongs to another owner.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
        try:
            guild_id, url = await view.manager.oauth.finish(
                view.alias, view.state, interaction.user.id, self.callback_url.value
            )
            await view.manager.invalidate_server(view.alias)
            server = (await view.manager.config.mcp_servers()).get(view.alias)
            if not server or server["url"] != url:
                raise MCPError(
                    "The server changed during sign-in. Remove and add it again."
                )
            tools = await view.manager.tools_for_mcp_server(
                guild_id, view.alias, server, refresh=True
            )
            async with view.manager.oauth.lock(view.alias):
                pending = view.manager.oauth.pending.get(view.alias)
                if not pending or pending["state"] != view.state:
                    raise MCPError(
                        "This login was cancelled or replaced. Remove and add the server again."
                    )
                server = (await view.manager.config.mcp_servers()).get(view.alias)
                if not server or server["url"] != url:
                    raise MCPError(
                        "The server changed during sign-in. Remove and add it again."
                    )
                view.manager.oauth.pending.pop(view.alias, None)
            await view.auth_view.finish(True)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="MCP authentication configured",
                    description=(
                        f"`{view.alias}` is ready with {len(tools)} tools. Enable it for a Discord server when ready.\n"
                        "This account is shared bot-wide for this alias."
                    ),
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
            await view.message.edit(
                embed=discord.Embed(
                    title="MCP sign-in completed",
                    description=f"`{view.alias}` authentication is configured.",
                    color=discord.Color.green(),
                ),
                content=None,
                view=None,
            )
            view.stop()
        except MCPError as exc:
            logger.warning(
                "MCP onboarding failed for %s (%s)", view.alias, type(exc).__name__
            )
            await view.auth_view.finish(False)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="MCP sign-in failed",
                    description=str(exc),
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
        except Exception as exc:
            logger.warning(
                "MCP onboarding failed for %s (%s)", view.alias, type(exc).__name__
            )
            await view.auth_view.finish(False)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="MCP sign-in failed",
                    description="Remove and add the server again to retry.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )

    async def on_error(self, interaction, error):
        # Discord's default handler logs a traceback, which may contain secrets.
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Sign-in failed. Remove and add the server again to retry.",
                ephemeral=True,
            )


class MCPLoginView(discord.ui.View):
    def __init__(self, manager, alias, owner_id, link, state, auth_view):
        super().__init__(timeout=LOGIN_SECONDS)
        self.manager = manager
        self.alias = alias
        self.owner_id = owner_id
        self.state = state
        self.auth_view = auth_view
        self.message = None
        sign_in = discord.ui.Button(label="Sign in", url=link)
        self.add_item(sign_in)
        self._children.insert(0, self._children.pop())

    async def interaction_check(self, interaction):
        if interaction.user.id == self.owner_id and await self.manager.bot.is_owner(
            interaction.user
        ):
            return True
        await interaction.response.send_message(
            embed=discord.Embed(
                title="MCP sign-in denied",
                description="Only the owner who started this login can use it.",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Paste URL", style=discord.ButtonStyle.primary)
    async def paste(self, interaction, button):
        await interaction.response.send_modal(MCPCallbackModal(self))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await interaction.response.defer()
        async with self.manager.oauth.lock(self.alias):
            pending = self.manager.oauth.pending.get(self.alias)
            if pending and pending["state"] == self.state:
                self.manager.oauth.pending.pop(self.alias, None)
        await interaction.edit_original_response(
            embed=discord.Embed(
                title="MCP sign-in cancelled",
                description="Remove and add the server again to retry.",
                color=discord.Color.orange(),
            ),
            content=None,
            view=None,
        )
        self.stop()

    async def on_timeout(self):
        async with self.manager.oauth.lock(self.alias):
            pending = self.manager.oauth.pending.get(self.alias)
            if pending and pending["state"] == self.state:
                self.manager.oauth.pending.pop(self.alias, None)
        if self.message:
            try:
                await self.message.edit(
                    embed=discord.Embed(
                        title="MCP sign-in expired",
                        description="Remove and add the server again to start over.",
                        color=discord.Color.orange(),
                    ),
                    content=None,
                    view=None,
                )
            except discord.HTTPException:
                pass

    async def on_error(self, interaction, error, item):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="MCP sign-in failed",
                    description="Remove and add the server again to retry.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
