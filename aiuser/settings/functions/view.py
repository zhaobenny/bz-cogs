from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

from aiuser.config.defaults import DEFAULT_TOOL_CALL_ROUNDS
from aiuser.config.model_info import get_model_info
from aiuser.functions import names
from aiuser.functions.scrape.providers import (
    FIRECRAWL as SCRAPE_FIRECRAWL,
)
from aiuser.functions.scrape.providers import (
    NATIVE as SCRAPE_NATIVE,
)
from aiuser.functions.search.providers import (
    NATIVE as SEARCH_NATIVE,
)
from aiuser.functions.search.providers import (
    PROVIDER_KEY_SERVICES as SEARCH_KEY_SERVICES,
)
from aiuser.functions.search.providers import (
    SEARXNG as SEARCH_SEARXNG,
)
from aiuser.providers.llm.codex.chatgpt import CODEX_ENDPOINT_MODE
from aiuser.providers.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_kind,
    is_openrouter_endpoint,
)
from aiuser.providers.speech.tts import DEFAULT_MODELS, DEFAULT_VOICES
from aiuser.settings.functions.utilities import provider_key_error
from aiuser.utils.utilities import truncate_text

if TYPE_CHECKING:
    from redbot.core import commands

BUILTIN_TOOL_NAMES: tuple[str, ...] = (
    names.SEARCH_WEB,
    names.OPEN_URL,
    names.IMAGE_REQUEST,
    names.VOICE_REQUEST,
    names.GET_WEATHER,
    names.IS_DAYTIME,
    names.ASK_WOLFRAM_ALPHA,
    names.RUN_PYTHON_CODE,
    names.READ_MEMORY,
    names.SAVE_MEMORY,
    names.ADD_REACTION,
    names.GET_DISCORD_INFO,
    names.DO_NOT_RESPOND,
)


@dataclass(frozen=True)
class ToolToggleEntry:
    key: str
    label: str
    tool_names: tuple[str, ...]
    description: str


TOOL_TOGGLE_ENTRIES: tuple[ToolToggleEntry, ...] = (
    ToolToggleEntry("search", "Search", (names.SEARCH_WEB,), "Search the web"),
    ToolToggleEntry("scrape", "Scrape", (names.OPEN_URL,), "Read web pages"),
    ToolToggleEntry("image", "Image", (names.IMAGE_REQUEST,), "Generate images"),
    ToolToggleEntry("voice", "Voice", (names.VOICE_REQUEST,), "Generate voice audio"),
    ToolToggleEntry(
        "weather_forecast",
        "Weather: Forecasts",
        (names.GET_WEATHER,),
        "Check weather forecasts",
    ),
    ToolToggleEntry(
        "weather_daytime",
        "Weather: Daytime",
        (names.IS_DAYTIME,),
        "Check if it is daytime",
    ),
    ToolToggleEntry(
        "wolfram_alpha",
        "Wolfram Alpha",
        (names.ASK_WOLFRAM_ALPHA,),
        "Query Wolfram Alpha",
    ),
    ToolToggleEntry(
        "code_runner",
        "Code Runner",
        (names.RUN_PYTHON_CODE,),
        "Run Python code via Modal",
    ),
    ToolToggleEntry(
        "memory",
        "Memory",
        (names.READ_MEMORY, names.SAVE_MEMORY),
        "Read and save server memories",
    ),
    ToolToggleEntry(
        "discord_reactions",
        "Discord: Reactions",
        (names.ADD_REACTION,),
        "Add reactions to messages",
    ),
    ToolToggleEntry(
        "discord_info",
        "Discord: Info",
        (names.GET_DISCORD_INFO,),
        "Look up Discord server info",
    ),
    ToolToggleEntry(
        "no_response",
        "No Response",
        (names.DO_NOT_RESPOND,),
        "Let the bot choose not to reply",
    ),
)


@dataclass(frozen=True)
class ToolSettingsSnapshot:
    enabled: bool
    enabled_tools: tuple[str, ...]
    tool_call_rounds: int
    current_model: str
    model_supports_tools: bool
    query_memories: bool
    search_provider: str
    search_endpoint: str | None
    search_max_results: int
    scrape_provider: str
    image_endpoint: str | None
    image_model: str | None
    image_preprompt: str | None
    voice_provider: str
    voice_model: str | None
    voice_name: str | None
    all_mcp_servers: tuple[str, ...]
    enabled_mcp_servers: tuple[str, ...]


async def load_tool_settings_snapshot(
    cog, guild: discord.Guild
) -> ToolSettingsSnapshot:
    guild_conf = cog.config.guild(guild)
    enabled = bool(await guild_conf.function_calling())
    enabled_tools = tuple(await guild_conf.function_calling_functions() or [])
    tool_call_rounds = (
        await guild_conf.function_calling_tool_call_rounds() or DEFAULT_TOOL_CALL_ROUNDS
    )
    current_model = await guild_conf.model() or await cog.config.default_model() or ""
    model_supports_tools = get_model_info(current_model).supports_tools
    query_memories = bool(await guild_conf.query_memories())

    search_provider = (
        await guild_conf.function_calling_search_provider() or "exa"
    ).strip()
    search_endpoint = await guild_conf.function_calling_search_endpoint()
    search_max_results = await guild_conf.function_calling_search_max_results()
    scrape_provider = (
        await guild_conf.function_calling_scrape_provider() or "local"
    ).strip()

    image_endpoint = await guild_conf.function_calling_image_custom_endpoint()
    image_model = await guild_conf.function_calling_image_model()
    image_preprompt = await guild_conf.function_calling_image_preprompt()

    voice_provider = (
        await guild_conf.function_calling_voice_provider() or "openai"
    ).strip()
    voice_provider_key = voice_provider.lower()
    voice_model = await guild_conf.function_calling_voice_model() or DEFAULT_MODELS.get(
        voice_provider_key
    )
    voice_name = await guild_conf.function_calling_voice() or DEFAULT_VOICES.get(
        voice_provider_key
    )

    configured_mcp = sorted((await cog.config.mcp_servers() or {}).keys())
    configured_mcp_set = set(configured_mcp)
    enabled_mcp = sorted(
        server
        for server in (await guild_conf.mcp_enabled_servers() or [])
        if server in configured_mcp_set
    )

    return ToolSettingsSnapshot(
        enabled=enabled,
        enabled_tools=enabled_tools,
        tool_call_rounds=tool_call_rounds,
        current_model=current_model,
        model_supports_tools=model_supports_tools,
        query_memories=query_memories,
        search_provider=search_provider,
        search_endpoint=search_endpoint,
        search_max_results=search_max_results,
        scrape_provider=scrape_provider,
        image_endpoint=image_endpoint,
        image_model=image_model,
        image_preprompt=image_preprompt,
        voice_provider=voice_provider,
        voice_model=voice_model,
        voice_name=voice_name,
        all_mcp_servers=tuple(configured_mcp),
        enabled_mcp_servers=tuple(enabled_mcp),
    )


def _format_subtools(
    enabled_set: set[str],
    items: tuple[tuple[str, str], ...],
    extra_notes: list[str] | None = None,
) -> str:
    on_labels = [label for tool_name, label in items if tool_name in enabled_set]
    off_labels = [label for tool_name, label in items if tool_name not in enabled_set]
    notes = []
    if off_labels:
        notes.append(f"{', '.join(off_labels)} off")
    if extra_notes:
        notes.extend(extra_notes)
    summary = ", ".join(on_labels)
    if notes:
        return f"{summary} *({', '.join(notes)})*"
    return summary


def build_tool_settings_embed(
    snapshot: ToolSettingsSnapshot, color: discord.Color, prefix: str
) -> discord.Embed:
    enabled_set = set(snapshot.enabled_tools)
    enabled_builtin_count = sum(
        1 for tool_name in BUILTIN_TOOL_NAMES if tool_name in enabled_set
    )

    status_badge = "🟢 **Enabled**" if snapshot.enabled else "🔴 **Disabled**"
    builtin_label = "built-in" if snapshot.enabled else "selected"
    header_parts = [
        status_badge,
        f"`{enabled_builtin_count}/{len(BUILTIN_TOOL_NAMES)}` {builtin_label}",
    ]
    if snapshot.all_mcp_servers:
        header_parts.append(
            f"`{len(snapshot.enabled_mcp_servers)}/{len(snapshot.all_mcp_servers)}` MCP"
        )
    header_parts.append(f"Max rounds: `{snapshot.tool_call_rounds}`")

    description_lines = [" · ".join(header_parts)]
    if (
        snapshot.enabled
        and not snapshot.model_supports_tools
        and snapshot.current_model
    ):
        description_lines.append(
            f"⚠️ `{truncate_text(snapshot.current_model, 120)}` may not support tool calling."
        )

    embed = discord.Embed(
        title="Tool Settings",
        description="\n".join(description_lines),
        color=color,
    )

    active_lines: list[str] = []
    disabled_groups: list[str] = []

    if names.SEARCH_WEB in enabled_set:
        provider_key = snapshot.search_provider.lower()
        if provider_key == SEARCH_NATIVE:
            search_detail = f"`{snapshot.search_provider}`"
        else:
            search_parts = [f"`{snapshot.search_provider}`"]
            if provider_key == SEARCH_SEARXNG:
                endpoint = (
                    truncate_text(snapshot.search_endpoint, 60)
                    if snapshot.search_endpoint
                    else "endpoint not set"
                )
                search_parts.append(f"`{endpoint}`")
            search_parts.append(f"max `{snapshot.search_max_results}` results")
            search_detail = ", ".join(search_parts)
        active_lines.append(f"• **Search** · {search_detail}")
    else:
        disabled_groups.append("Search")

    if names.OPEN_URL in enabled_set:
        active_lines.append(f"• **Scrape** · `{snapshot.scrape_provider}`")
    else:
        disabled_groups.append("Scrape")

    if names.IMAGE_REQUEST in enabled_set:
        image_model = (
            truncate_text(snapshot.image_model, 50)
            if snapshot.image_model
            else "Default"
        )
        image_endpoint = (
            truncate_text(snapshot.image_endpoint, 50)
            if snapshot.image_endpoint
            else "Autodetected"
        )
        image_parts = [f"model `{image_model}`", f"endpoint `{image_endpoint}`"]
        if snapshot.image_preprompt:
            image_parts.append("preprompt set")
        active_lines.append(f"• **Image** · {', '.join(image_parts)}")
    else:
        disabled_groups.append("Image")

    if names.VOICE_REQUEST in enabled_set:
        voice_parts = [f"`{snapshot.voice_provider}`"]
        if snapshot.voice_model:
            voice_parts.append(f"model `{truncate_text(snapshot.voice_model, 50)}`")
        if snapshot.voice_name:
            voice_parts.append(f"voice `{truncate_text(snapshot.voice_name, 50)}`")
        active_lines.append(f"• **Voice** · {', '.join(voice_parts)}")
    else:
        disabled_groups.append("Voice")

    weather_items = (
        (names.GET_WEATHER, "forecasts"),
        (names.IS_DAYTIME, "daytime"),
    )
    if any(tool_name in enabled_set for tool_name, _ in weather_items):
        active_lines.append(
            f"• **Weather** · {_format_subtools(enabled_set, weather_items)}"
        )
    else:
        disabled_groups.append("Weather")

    if names.ASK_WOLFRAM_ALPHA in enabled_set:
        active_lines.append("• **Wolfram Alpha**")
    else:
        disabled_groups.append("Wolfram Alpha")

    if names.RUN_PYTHON_CODE in enabled_set:
        active_lines.append("• **Code Runner**")
    else:
        disabled_groups.append("Code Runner")

    memory_items = (
        (names.READ_MEMORY, "read"),
        (names.SAVE_MEMORY, "save"),
    )
    if any(tool_name in enabled_set for tool_name, _ in memory_items):
        memory_notes = [] if snapshot.query_memories else ["⚠️ retrieval off"]
        active_lines.append(
            f"• **Memory** · {_format_subtools(enabled_set, memory_items, memory_notes)}"
        )
    else:
        disabled_groups.append("Memory")

    discord_items = (
        (names.ADD_REACTION, "reactions"),
        (names.GET_DISCORD_INFO, "info"),
    )
    if any(tool_name in enabled_set for tool_name, _ in discord_items):
        active_lines.append(
            f"• **Discord** · {_format_subtools(enabled_set, discord_items)}"
        )
    else:
        disabled_groups.append("Discord")

    if names.DO_NOT_RESPOND in enabled_set:
        active_lines.append("• **No Response**")
    else:
        disabled_groups.append("No Response")

    active_title = "Enabled Tools" if snapshot.enabled else "Selected Tools (Paused)"
    embed.add_field(
        name=active_title,
        value=truncate_text("\n".join(active_lines), 1024) if active_lines else "None",
        inline=False,
    )

    if disabled_groups:
        embed.add_field(
            name="Disabled Tools",
            value=" · ".join(disabled_groups),
            inline=False,
        )

    if snapshot.all_mcp_servers:
        enabled_mcp_set = set(snapshot.enabled_mcp_servers)
        disabled_mcp = [
            server
            for server in snapshot.all_mcp_servers
            if server not in enabled_mcp_set
        ]
        mcp_lines = []
        if snapshot.enabled_mcp_servers:
            enabled_list = ", ".join(
                f"`{name}`" for name in snapshot.enabled_mcp_servers
            )
            mcp_lines.append(f"Enabled: {enabled_list}")
        if disabled_mcp:
            disabled_list = ", ".join(f"`{name}`" for name in disabled_mcp)
            label = "Available" if not snapshot.enabled_mcp_servers else "Disabled"
            mcp_lines.append(f"{label}: {disabled_list}")
        embed.add_field(
            name="MCP Servers",
            value=truncate_text("\n".join(mcp_lines), 1024),
            inline=False,
        )

    embed.set_footer(
        text=f"{prefix}aiuser tools <tool> for provider and advanced settings"
    )
    return embed


async def _validate_tool_enable(
    cog, ctx: commands.Context, entry: ToolToggleEntry
) -> str | None:
    guild_conf = cog.config.guild(ctx.guild)
    if entry.key == "search":
        provider = (
            (await guild_conf.function_calling_search_provider() or "exa")
            .strip()
            .lower()
        )
        if provider == SEARCH_NATIVE:
            endpoint = await cog.config.custom_openai_endpoint()
            if endpoint == CODEX_ENDPOINT_MODE or get_openai_compat_kind(
                endpoint
            ) not in {
                CompatEndpointKind.OPENAI,
                CompatEndpointKind.OPENROUTER,
            }:
                return (
                    "Search: Native search requires an OpenAI or OpenRouter endpoint."
                )
        key_service = SEARCH_KEY_SERVICES.get(provider)
        if key_service:
            key_error = await provider_key_error(cog.bot, ctx, key_service)
            if key_error:
                return f"Search: {key_error}"
        if (
            provider == SEARCH_SEARXNG
            and not await guild_conf.function_calling_search_endpoint()
        ):
            return (
                "Search: SearXNG endpoint not set! Set it using "
                f"`{ctx.clean_prefix}aiuser tools search endpoint set <url>`."
            )
        return None

    if entry.key == "scrape":
        provider = (
            (await guild_conf.function_calling_scrape_provider() or "local")
            .strip()
            .lower()
        )
        if provider == SCRAPE_NATIVE and not is_openrouter_endpoint(
            await cog.config.custom_openai_endpoint()
        ):
            return "Scrape: Native web fetch requires an OpenRouter endpoint."
        if provider == SCRAPE_FIRECRAWL:
            key_error = await provider_key_error(cog.bot, ctx, provider)
            if key_error:
                return f"Scrape: {key_error}"
        return None

    if entry.key == "voice":
        provider = (
            (await guild_conf.function_calling_voice_provider() or "openai")
            .strip()
            .lower()
        )
        key_error = await provider_key_error(cog.bot, ctx, provider)
        if key_error:
            return f"Voice: {key_error}"
        return None

    if entry.key == "wolfram_alpha":
        key_error = await provider_key_error(
            cog.bot, ctx, "wolfram_alpha", key_name="app_id"
        )
        if key_error:
            return f"Wolfram Alpha: {key_error}"
        return None

    if entry.key == "code_runner":
        tokens = await cog.bot.get_shared_api_tokens("modal")
        if not tokens.get("token_id") and not tokens.get("token_secret"):
            return (
                "Code Runner: [Modal.com](<https://modal.com/settings/>) API Token not set! "
                f"Set them using `{ctx.clean_prefix}set api modal token_id,TOKENID` and "
                f"`{ctx.clean_prefix}set api modal token_secret,TOKENSECRET`."
            )
        return None

    return None


def _entry_description(entry: ToolToggleEntry, snapshot: ToolSettingsSnapshot) -> str:
    if entry.key == "search":
        return truncate_text(f"Web search ({snapshot.search_provider})", 100)
    if entry.key == "scrape":
        return truncate_text(f"Read web pages ({snapshot.scrape_provider})", 100)
    if entry.key == "image":
        model = snapshot.image_model or "Default"
        return truncate_text(f"Generate images ({model})", 100)
    if entry.key == "voice":
        return truncate_text(f"Generate voice ({snapshot.voice_provider})", 100)
    return entry.description


class MaxRoundsModal(discord.ui.Modal, title="Set max tool-call rounds"):
    def __init__(self, view: ToolSettingsView, current_rounds: int):
        super().__init__(timeout=300)
        self.tool_view = view
        self.rounds_input = discord.ui.TextInput(
            label="Rounds per response",
            default=str(current_rounds),
            placeholder="e.g. 10",
            max_length=4,
        )
        self.add_item(self.rounds_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await self.tool_view.interaction_check(interaction):
            return
        if self.tool_view.is_finished():
            return await interaction.response.send_message(
                f"This menu has timed out. Run `{self.tool_view.ctx.clean_prefix}aiuser tools status` again.",
                ephemeral=True,
            )
        raw_value = str(self.rounds_input).strip()
        try:
            rounds = int(raw_value)
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a positive whole number.", ephemeral=True
            )
        if rounds < 1:
            return await interaction.response.send_message(
                "Please enter a positive whole number.", ephemeral=True
            )

        await self.tool_view.cog.config.guild(
            self.tool_view.ctx.guild
        ).function_calling_tool_call_rounds.set(rounds)
        embed = await self.tool_view.refresh()
        await interaction.response.edit_message(embed=embed, view=self.tool_view)


class ToolSettingsView(discord.ui.View):
    def __init__(
        self,
        cog,
        ctx: commands.Context,
        color: discord.Color,
        snapshot: ToolSettingsSnapshot,
    ):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.color = color
        self.snapshot = snapshot
        self.message: discord.Message | None = None
        self._rebuild_items()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id and await self.cog.bot.is_owner(
            interaction.user
        ):
            return True
        await interaction.response.send_message(
            "Only the bot owner who opened this menu can change tool settings.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,
    ):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Couldn't update tool settings. Check Red's logs and try again.",
                ephemeral=True,
            )

    def build_embed(self) -> discord.Embed:
        return build_tool_settings_embed(
            self.snapshot, self.color, self.ctx.clean_prefix
        )

    async def refresh(self) -> discord.Embed:
        self.snapshot = await load_tool_settings_snapshot(self.cog, self.ctx.guild)
        self._rebuild_items()
        return self.build_embed()

    def _rebuild_items(self) -> None:
        self.clear_items()
        enabled_set = set(self.snapshot.enabled_tools)

        tool_select = discord.ui.Select(
            placeholder="Toggle a built-in tool...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=entry.label,
                    value=entry.key,
                    emoji=(
                        "🟢"
                        if any(tool in enabled_set for tool in entry.tool_names)
                        else "⚪"
                    ),
                    description=_entry_description(entry, self.snapshot),
                )
                for entry in TOOL_TOGGLE_ENTRIES
            ],
            row=0,
        )
        tool_select.callback = self._on_tools_select
        self.add_item(tool_select)

        button_row = 1
        if self.snapshot.all_mcp_servers:
            enabled_mcp_set = set(self.snapshot.enabled_mcp_servers)
            prioritized = list(self.snapshot.enabled_mcp_servers) + [
                name
                for name in self.snapshot.all_mcp_servers
                if name not in enabled_mcp_set
            ]
            visible_mcp = prioritized[:25]
            mcp_select = discord.ui.Select(
                placeholder="Toggle an MCP server...",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(
                        label=name[:100],
                        value=name,
                        emoji="🟢" if name in enabled_mcp_set else "⚪",
                        description="Enabled"
                        if name in enabled_mcp_set
                        else "Disabled",
                    )
                    for name in visible_mcp
                ],
                row=1,
            )
            mcp_select.callback = self._on_mcp_select
            self.add_item(mcp_select)
            button_row = 2

        toggle_button = discord.ui.Button(
            label="Disable Tools" if self.snapshot.enabled else "Enable Tools",
            style=(
                discord.ButtonStyle.secondary
                if self.snapshot.enabled
                else discord.ButtonStyle.success
            ),
            row=button_row,
        )
        toggle_button.callback = self._on_toggle_master
        self.add_item(toggle_button)

        rounds_button = discord.ui.Button(
            label="Max Rounds",
            style=discord.ButtonStyle.secondary,
            row=button_row,
        )
        rounds_button.callback = self._on_max_rounds
        self.add_item(rounds_button)

    async def _on_tools_select(self, interaction: discord.Interaction):
        values = interaction.data.get("values", [])
        if not values:
            return await interaction.response.defer()
        entry = next(
            (item for item in TOOL_TOGGLE_ENTRIES if item.key == values[0]),
            None,
        )
        if entry is None:
            return await interaction.response.defer()

        guild_conf = self.cog.config.guild(self.ctx.guild)
        current_tools = list(await guild_conf.function_calling_functions() or [])
        current_set = set(current_tools)
        was_enabled = any(tool in current_set for tool in entry.tool_names)

        error: str | None = None
        note: str | None = None

        if not was_enabled:
            error = await _validate_tool_enable(self.cog, self.ctx, entry)
            if not error:
                for tool_name in entry.tool_names:
                    if tool_name not in current_tools:
                        current_tools.append(tool_name)
                await guild_conf.function_calling_functions.set(current_tools)
                await guild_conf.function_calling.set(True)
                if entry.key == "memory" and not await guild_conf.query_memories():
                    note = (
                        "Saved memory retrieval is still off. Enable it with "
                        f"`{self.ctx.clean_prefix}aiuser memory enable`."
                    )
        else:
            remove_set = set(entry.tool_names)
            current_tools = [
                tool_name for tool_name in current_tools if tool_name not in remove_set
            ]
            await guild_conf.function_calling_functions.set(current_tools)

        embed = await self.refresh()
        await interaction.response.edit_message(embed=embed, view=self)

        feedback = error or note
        if feedback:
            await interaction.followup.send(
                truncate_text(feedback, 1900), ephemeral=True
            )

    async def _on_mcp_select(self, interaction: discord.Interaction):
        values = interaction.data.get("values", [])
        if not values:
            return await interaction.response.defer()
        name = values[0]

        guild_conf = self.cog.config.guild(self.ctx.guild)
        current_enabled = list(await guild_conf.mcp_enabled_servers() or [])
        if name in current_enabled:
            new_enabled = [server for server in current_enabled if server != name]
            await guild_conf.mcp_enabled_servers.set(new_enabled)
            if self.cog.services is not None:
                await self.cog.services.mcp.invalidate(self.ctx.guild.id, name)
        else:
            configured = await self.cog.config.mcp_servers() or {}
            if name not in configured:
                embed = await self.refresh()
                await interaction.response.edit_message(embed=embed, view=self)
                return await interaction.followup.send(
                    f"Unknown MCP server `{truncate_text(name)}`.", ephemeral=True
                )
            current_enabled.append(name)
            await guild_conf.mcp_enabled_servers.set(current_enabled)
            await guild_conf.function_calling.set(True)

        embed = await self.refresh()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_toggle_master(self, interaction: discord.Interaction):
        guild_conf = self.cog.config.guild(self.ctx.guild)
        new_enabled = not await guild_conf.function_calling()
        await guild_conf.function_calling.set(new_enabled)
        embed = await self.refresh()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_max_rounds(self, interaction: discord.Interaction):
        rounds = (
            await self.cog.config.guild(
                self.ctx.guild
            ).function_calling_tool_call_rounds()
            or DEFAULT_TOOL_CALL_ROUNDS
        )
        await interaction.response.send_modal(MaxRoundsModal(self, rounds))
