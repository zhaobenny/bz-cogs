from __future__ import annotations

import asyncio
import logging
import re
from enum import Enum, IntEnum

import discord
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, AuthenticationError

from aiuser.config.constants import OPENROUTER_API_V1_URL
from aiuser.config.defaults import DEFAULT_LLM_MODEL, DEFAULT_PRESETS
from aiuser.config.model_info import get_model_info
from aiuser.providers.llm.codex.chatgpt import load as load_chatgpt_credentials
from aiuser.providers.llm.openai_compatible.client import invalidate_openai_client
from aiuser.providers.llm.openai_compatible.endpoints import (
    get_openai_compat_kind,
)
from aiuser.providers.llm.openai_compatible.provider import list_openai_compat_models
from aiuser.providers.llm.registry import get_llm_provider

log = logging.getLogger("red.bz_cogs.aiuser.setup")


class SetupStep(IntEnum):
    PROVIDER = 0
    MODEL = 1
    CHANNEL = 2
    FREQUENCY = 3
    PERSONALITY = 4
    ABILITIES = 5


class ProviderState(Enum):
    UNCONFIGURED = "unconfigured"
    CONFIGURED = "configured"
    CHECKING = "checking"
    VERIFIED = "verified"
    FAILED = "failed"


NEXT_STEP = {
    SetupStep.PROVIDER: SetupStep.MODEL,
    SetupStep.MODEL: SetupStep.CHANNEL,
    SetupStep.CHANNEL: SetupStep.FREQUENCY,
    SetupStep.FREQUENCY: SetupStep.PERSONALITY,
    SetupStep.PERSONALITY: SetupStep.ABILITIES,
}
PREVIOUS_STEP = {next_step: step for step, next_step in NEXT_STEP.items()}


class ProviderKeyModal(discord.ui.Modal, title="Connect provider"):
    def __init__(self, view, provider):
        super().__init__(timeout=(view.timeout or 1800) + 1800)
        self.wizard = view
        self.provider = provider if provider in {"openai", "openrouter"} else "openai"
        self.provider_revision = view.provider_revision
        if hasattr(discord.ui, "Label"):
            self.key = discord.ui.TextInput(max_length=512)
            self.provider_field = discord.ui.Select(
                options=[
                    discord.SelectOption(
                        label=label, value=value, default=value == self.provider
                    )
                    for label, value in (
                        ("OpenAI", "openai"),
                        ("OpenRouter", "openrouter"),
                    )
                ]
            )
            self.add_item(
                discord.ui.Label(
                    text="LLM provider",
                    component=self.provider_field,
                )
            )
            self.add_item(
                discord.ui.Label(
                    text="API key",
                    component=self.key,
                )
            )
        else:
            self.key = discord.ui.TextInput(
                label="API key",
                max_length=512,
            )
            self.provider_field = discord.ui.TextInput(
                label="LLM provider",
                placeholder="openai or openrouter",
                default=self.provider,
                max_length=10,
            )
            self.add_item(self.provider_field)
            self.add_item(self.key)

    async def on_submit(self, interaction):
        if not await self.wizard.interaction_check(interaction):
            return
        if self.wizard.is_finished():
            message = (
                "Setup timed out. Run `{prefix}aiuser setup` to start again."
                if self.wizard.timed_out
                else "Setup has ended. Run `{prefix}aiuser setup` to start again."
            ).format(prefix=self.wizard.ctx.clean_prefix)
            return await interaction.response.send_message(message, ephemeral=True)
        if self.wizard.provider_revision != self.provider_revision:
            return await interaction.response.send_message(
                "This form is out of date. Open it again.", ephemeral=True
            )
        if self.wizard.timeout is not None:
            self.wizard.timeout = self.wizard.timeout
        if isinstance(self.provider_field, discord.ui.Select):
            provider = (
                self.provider_field.values[0] if self.provider_field.values else ""
            )
        else:
            provider = str(self.provider_field).strip().lower()
        if provider not in {"openai", "openrouter"}:
            return await interaction.response.send_message(
                "Choose OpenAI or OpenRouter first.",
                ephemeral=True,
            )
        if provider != self.wizard.provider_choice:
            self.wizard.provider_choice = provider
            self.wizard.provider_revision += 1
            self.provider_revision = self.wizard.provider_revision
            self.wizard.models = None
        self.provider = provider
        await interaction.response.defer()
        key = str(self.key).strip()
        if not key:
            return await interaction.followup.send("Enter an API key.", ephemeral=True)
        endpoint = OPENROUTER_API_V1_URL if self.provider == "openrouter" else None
        client = AsyncOpenAI(api_key=key, base_url=endpoint)
        try:
            models = await asyncio.wait_for(
                list_openai_compat_models(client, endpoint), timeout=20
            )
        # Show a generic setup error for unexpected provider failures.
        except Exception as error:  # noqa: BLE001
            log.warning("API key verification failed (%s).", type(error).__name__)
            if self.wizard.is_finished():
                message = (
                    "Setup timed out. Run `{prefix}aiuser setup` to start again."
                    if self.wizard.timed_out
                    else "Setup has ended. Run `{prefix}aiuser setup` to start again."
                ).format(prefix=self.wizard.ctx.clean_prefix)
                return await interaction.followup.send(message, ephemeral=True)
            if self.wizard.provider_revision != self.provider_revision:
                return await interaction.followup.send(
                    "This form is out of date. Open it again.", ephemeral=True
                )
            if isinstance(error, AuthenticationError):
                self.wizard.provider_error = "The provider rejected this key. Check the key and try again. See Red's logs for details."
            elif isinstance(
                error, (APIConnectionError, APITimeoutError, asyncio.TimeoutError)
            ):
                self.wizard.provider_error = "Couldn't reach the provider. Check your network and Red's logs, then retry."
            else:
                self.wizard.provider_error = (
                    "Couldn't verify the provider. Check Red's logs for details."
                )
            self.wizard.provider_state = ProviderState.FAILED
            self.wizard.retry_available = False
            self.wizard.update_items()
            try:
                return await interaction.edit_original_response(**self.wizard.display())
            except discord.HTTPException:
                self.wizard.stop()
                return await interaction.followup.send(
                    self.wizard.provider_error, ephemeral=True
                )
        finally:
            await client.close()
        if self.wizard.is_finished():
            message = (
                "Setup timed out. Run `{prefix}aiuser setup` to start again."
                if self.wizard.timed_out
                else "Setup has ended. Run `{prefix}aiuser setup` to start again."
            ).format(prefix=self.wizard.ctx.clean_prefix)
            return await interaction.followup.send(message, ephemeral=True)
        if self.wizard.provider_revision != self.provider_revision:
            return await interaction.followup.send(
                "This form is out of date. Open it again.", ephemeral=True
            )
        cog = self.wizard.cog
        previous = await cog.config.custom_openai_endpoint()
        await cog._save_current_endpoint_models(previous)
        await cog.bot.set_shared_api_tokens(self.provider, api_key=key)
        await cog.config.custom_openai_endpoint.set(endpoint)
        await invalidate_openai_client(cog.services)
        if previous != endpoint:
            cog.services.context_cache.clear()
            default = (
                f"openai/{DEFAULT_LLM_MODEL}"
                if self.provider == "openrouter"
                else DEFAULT_LLM_MODEL
            )
            await cog._restore_endpoint_models(
                endpoint_url=endpoint, chat_model=default, image_model=default
            )
        provider_ready = await self.wizard.check_provider()
        if self.wizard.is_finished():
            return await interaction.followup.send(
                f"API key saved, but setup has already ended. Run `{self.wizard.ctx.clean_prefix}aiuser setup` to continue.",
                ephemeral=True,
            )
        self.wizard.provider_state = (
            ProviderState.VERIFIED if provider_ready else ProviderState.UNCONFIGURED
        )
        self.wizard.provider_error = None
        self.wizard.retry_available = False
        self.wizard.models = models
        self.wizard.model = None
        self.wizard.update_items()
        try:
            await interaction.edit_original_response(**self.wizard.display())
        except discord.HTTPException as error:
            log.warning(
                "Could not update the setup message (%s).", type(error).__name__
            )
            self.wizard.stop()
            await interaction.followup.send(
                f"API key saved, but the setup message couldn't be updated. Check Red's logs or run `{self.wizard.ctx.clean_prefix}aiuser setup` to continue.",
                ephemeral=True,
            )

    async def on_error(self, interaction, error):
        log.warning("API key setup failed (%s).", type(error).__name__)
        message = "Couldn't complete provider setup. Check Red's logs and try again."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class OnboardingView(discord.ui.View):
    def __init__(self, cog, ctx, settings, provider_ready):
        super().__init__(timeout=1800)
        self.cog = cog
        self.ctx = ctx
        self.settings = settings
        self.provider_state = (
            ProviderState.CONFIGURED if provider_ready else ProviderState.UNCONFIGURED
        )
        self.provider_error = None
        self.retry_available = False
        self.provider_revision = 0
        endpoint = settings.get("endpoint")
        active = get_openai_compat_kind(endpoint).value if endpoint != "codex" else ""
        self.provider_choice = active or "openai"
        self.channel = None
        self.added_channel_id = None
        self.chance = None
        for option in self.choose_chance.options:
            option.default = float(option.value) == settings.get("reply_percent")
        self.original_guild_prompt = settings.get("custom_text_prompt")
        prompt = (
            settings.get("custom_text_prompt")
            or settings.get("global_prompt")
            or DEFAULT_PRESETS["cynical"]
        )
        self.persona = next(
            (name for name, value in DEFAULT_PRESETS.items() if value == prompt), None
        )
        for option in self.choose_persona.options:
            option.default = option.value == self.persona
        self.initial_images_enabled = bool(settings.get("scan_images"))
        self.initial_tools_enabled = bool(settings.get("function_calling"))
        self.model = None
        self.models = None
        self.default_model = settings.get("default_model", "")
        self.message = None
        self.timed_out = False
        self.step = SetupStep.PROVIDER
        self.update_items()

    def update_items(self):
        self.clear_items()
        if self.step == SetupStep.MODEL and self.models:
            choices = list(
                dict.fromkeys(
                    item
                    for item in self.models
                    if isinstance(item, str) and 0 < len(item) <= 100
                )
            )
            current = self.model or self.settings.get("model") or self.default_model

            def version(item):
                match = re.search(
                    r"(?:gpt|claude|gemini)(?:[-_.](?:sonnet|opus|haiku|flash|pro))?[-_.]?(\d+(?:\.\d+|[-_]\d{1,2}(?!\d)){0,2})",
                    item.lower(),
                )
                return (
                    tuple(int(part) for part in re.findall(r"\d+", match.group(1)))
                    if match
                    else ()
                )

            if self.provider_choice == "openrouter":
                pinned = list(
                    dict.fromkeys(
                        item
                        for item in (current, self.default_model)
                        if item in choices
                    )
                )
                choices = pinned + [item for item in choices if item not in pinned]
            elif self.provider_choice == "openai":
                choices.sort(
                    key=lambda item: (
                        version(item),
                        not bool(
                            re.search(r"[-_]\d{4}[-_]\d{2}[-_]\d{2}(?:$|:)", item)
                        ),
                        item.lower(),
                    ),
                    reverse=True,
                )
                pinned = list(
                    dict.fromkeys(
                        item
                        for item in (current, self.default_model)
                        if item in choices
                    )
                )
                missing = [item for item in pinned if item not in choices[:25]]
                if missing:
                    choices = choices[: 25 - len(missing)] + missing
            else:
                choices.sort(
                    key=lambda item: (
                        item != current,
                        item != self.default_model,
                        item.lower(),
                    )
                )
            choices = choices[:25]
            if choices:
                select = discord.ui.Select(
                    placeholder="Choose from available models",
                    options=[
                        discord.SelectOption(
                            label=item[:100],
                            value=item,
                            default=item
                            == (
                                self.model
                                or self.settings.get("model")
                                or self.default_model
                            ),
                        )
                        for item in choices
                    ],
                )
                select.callback = self.select_model
                self.add_item(select)
        provider_controls = []
        if self.provider_state not in {
            ProviderState.VERIFIED,
            ProviderState.CHECKING,
        } or (self.provider_state is ProviderState.VERIFIED and self.models == []):
            if self.retry_available or (
                self.provider_choice in {"codex", "custom"}
                and self.provider_state
                in {ProviderState.FAILED, ProviderState.UNCONFIGURED}
            ):
                provider_controls.append(self.retry_provider)
            provider_controls.append(self.connect_provider)
        controls = [
            provider_controls,
            [],
            [self.choose_channel],
            [self.choose_chance],
            [self.choose_persona],
            [self.toggle_images, self.toggle_tools],
        ][self.step]
        self.toggle_images.label = "Images: {status}".format(
            status="On" if self.settings.get("scan_images") else "Off"
        )
        self.toggle_tools.label = "Tools: {status}".format(
            status="On" if self.settings.get("function_calling") else "Off"
        )
        if self.step == SetupStep.ABILITIES:
            info = get_model_info(
                self.model or self.settings.get("model") or self.default_model
            )
            controls = [
                button
                for button, available in (
                    (
                        self.toggle_images,
                        info.supports_vision
                        or self.settings.get("scan_images")
                        or self.initial_images_enabled,
                    ),
                    (
                        self.toggle_tools,
                        info.supports_tools
                        or self.settings.get("function_calling")
                        or self.initial_tools_enabled,
                    ),
                )
                if available
            ]
        for item in controls:
            self.add_item(item)
        if self.step:
            self.add_item(self.previous)
        active = (
            "codex"
            if self.settings.get("endpoint") == "codex"
            else get_openai_compat_kind(self.settings.get("endpoint")).value
        )
        self.next_step.disabled = self.step == SetupStep.PROVIDER and (
            self.provider_state is not ProviderState.VERIFIED
            or (self.provider_choice is not None and self.provider_choice != active)
        )
        if self.step == SetupStep.MODEL:
            self.next_step.disabled = bool(
                self.models is not None
                and not self.model
                and (self.settings.get("model") or self.default_model)
                not in self.models
            )
        if (
            self.step != SetupStep.PROVIDER
            or self.provider_state is ProviderState.VERIFIED
        ):
            self.add_item(
                self.finish if self.step == SetupStep.ABILITIES else self.next_step
            )
        if self.step != SetupStep.ABILITIES:
            self.add_item(self.skip)

    def display(self):
        text = self.summary()
        title, body = text.split("\n", 1)
        if self.step == SetupStep.PROVIDER:
            body += f"\nFor options not covered here, use `{self.ctx.clean_prefix}aiuser` or `{self.ctx.clean_prefix}aiuserowner`."
        embed = discord.Embed(
            title=title, description=body, color=discord.Color.blurple()
        )
        commands = [
            "Later steps show the command for each setting",
            f"{self.ctx.clean_prefix}aiuser model set",
            f"{self.ctx.clean_prefix}aiuser channels add",
            f"{self.ctx.clean_prefix}aiuser reply chance set",
            f"{self.ctx.clean_prefix}aiuser prompt",
            f"{self.ctx.clean_prefix}aiuser media images / functions",
        ]
        embed.set_footer(text=f"Step {self.step + 1} of 6 • {commands[self.step]}")
        return {"content": None, "embed": embed, "view": self}

    async def interaction_check(self, interaction):
        if interaction.user.id == self.ctx.author.id and await self.cog.bot.is_owner(
            interaction.user
        ):
            return True
        await interaction.response.send_message(
            "Only the bot owner who started setup can use these controls. Use the aiuser optin or optout command to make your own choice.",
            ephemeral=True,
        )
        return False

    def summary(self):
        prefix = self.ctx.clean_prefix
        if self.step == SetupStep.PROVIDER:
            prefix = self.settings.get("dm_prefix") or prefix
            endpoint = self.settings.get("endpoint")
            active = (
                "codex"
                if endpoint == "codex"
                else get_openai_compat_kind(endpoint).value
            )
            selected = self.provider_choice or active
            model = self.model or self.settings.get("model") or self.default_model
            if self.provider_state is ProviderState.CHECKING:
                return "LLM provider\nChecking your existing connection..."
            if (
                self.provider_choice in {"codex", "custom"}
                and self.provider_state is ProviderState.UNCONFIGURED
            ):
                return "LLM provider\nCouldn't check `{provider}`. {reason}".format(
                    provider=active,
                    reason="Retry or enter an API key.",
                )
            if self.provider_state is ProviderState.FAILED:
                if self.retry_available:
                    return "LLM provider\nCouldn't check `{provider}`. {reason}".format(
                        provider=active,
                        reason=self.provider_error
                        or "Check Red's logs, then retry or enter an API key.",
                    )
                return "LLM provider\n{provider_error}\nTap Enter API key to try again.".format(
                    provider_error=self.provider_error
                    or "Couldn't verify the provider. Check Red's logs for details."
                )
            if self.provider_state is ProviderState.VERIFIED and selected == active:
                return (
                    f"LLM provider\nConnected to `{active}`. Continue to the next step."
                )
            return "LLM provider\n{instructions}".format(
                instructions="Need a key? [OpenAI](<https://platform.openai.com/api-keys>) · [OpenRouter](<https://openrouter.ai/settings/keys>)"
            )
        if self.step == SetupStep.MODEL:
            model = self.model or self.settings.get("model") or self.default_model
            available_models = {
                item for item in self.models or [] if isinstance(item, str)
            }
            truncated = len(available_models) > 25
            if self.models is not None and not self.model and model not in self.models:
                if not self.models:
                    return "Choose a model\nNo models found. Go back and reconnect."
                message = "Choose a model\nChoose a model below to continue."
                if truncated:
                    message += "\nShowing a selection of models."
                return message
            message = f"Choose a model\nCurrent model: `{model}`."
            if truncated:
                message += "\nShowing a selection of models."
            return message
        if self.step == SetupStep.CHANNEL:
            channel = ""
            if self.channel:
                perms = self.channel.permissions_for(self.ctx.guild.me)
                missing = [
                    name
                    for enabled, name in (
                        (
                            perms.view_channel,
                            "View Channel",
                        ),
                        (
                            perms.send_messages,
                            "Send Messages",
                        ),
                        (
                            perms.read_message_history,
                            "Read Message History",
                        ),
                    )
                    if not enabled
                ]
                if missing:
                    channel += "\nRequired permissions missing: {permissions}.".format(
                        permissions=", ".join(missing)
                    )
            return f"Choose a channel to chat in\n{channel}"
        if self.step == SetupStep.FREQUENCY:
            chance = (
                f"{self.chance:.0%}"
                if self.chance is not None
                else f"{self.settings['reply_percent']:.0%}"
            )
            return f"How often should I reply?\nRandom chance after chat pauses: **{chance}**.\nMentions can also trigger replies."
        if self.step == SetupStep.PERSONALITY:
            return "Choose a personality\n"
        info = get_model_info(
            self.model or self.settings.get("model") or self.default_model
        )
        abilities = []
        if (
            info.supports_vision
            or self.settings.get("scan_images")
            or self.initial_images_enabled
        ):
            abilities.append("**Images:** Let the AI see images in messages.")
        if (
            info.supports_tools
            or self.settings.get("function_calling")
            or self.initial_tools_enabled
        ):
            abilities.append(
                f"**Tools:** Enable tool calling. See `{self.ctx.clean_prefix}aiuser tools status`."
            )
        return "Extra abilities\n{abilities}".format(
            abilities="\n".join(abilities)
            or "No extra abilities available for this model."
        )

    @discord.ui.button(
        label="Enter API key",
        style=discord.ButtonStyle.primary,
    )
    async def connect_provider(self, interaction, button):
        endpoint = self.settings.get("endpoint")
        provider = self.provider_choice or (
            "codex" if endpoint == "codex" else get_openai_compat_kind(endpoint).value
        )
        await interaction.response.send_modal(ProviderKeyModal(self, provider))

    @discord.ui.button(
        label="Retry",
        style=discord.ButtonStyle.secondary,
    )
    async def retry_provider(self, interaction, button):
        self.provider_state = ProviderState.CHECKING
        self.update_items()
        await interaction.response.edit_message(**self.display())
        await self.verify_existing_provider()
        if not self.is_finished():
            self.update_items()
            try:
                await interaction.message.edit(**self.display())
            except discord.HTTPException:
                self.stop()

    async def select_model(self, interaction):
        self.model = interaction.data["values"][0]
        await self.cog.config.guild(self.ctx.guild).model.set(self.model)
        self.update_items()
        await interaction.response.edit_message(**self.display())

    @discord.ui.button(
        label="Back",
        style=discord.ButtonStyle.secondary,
    )
    async def previous(self, interaction, button):
        if self.step == SetupStep.PROVIDER:
            return await interaction.response.defer()
        self.step = PREVIOUS_STEP[self.step]
        self.update_items()
        await interaction.response.edit_message(**self.display())

    @discord.ui.button(
        label="Next",
        style=discord.ButtonStyle.primary,
    )
    async def next_step(self, interaction, button):
        if self.step == SetupStep.ABILITIES:
            return await interaction.response.defer()
        active = (
            "codex"
            if self.settings.get("endpoint") == "codex"
            else get_openai_compat_kind(self.settings.get("endpoint")).value
        )
        if self.step == SetupStep.PROVIDER and (
            self.provider_state is not ProviderState.VERIFIED
            or (self.provider_choice is not None and self.provider_choice != active)
        ):
            return await interaction.response.send_message(
                "Connect and check your provider first.",
                ephemeral=True,
            )
        if self.step == SetupStep.MODEL and self.next_step.disabled:
            return await interaction.response.send_message(
                "Choose a model to continue.", ephemeral=True
            )
        if self.step == SetupStep.CHANNEL and not self.channel:
            return await interaction.response.send_message(
                "Choose a reply channel before continuing.",
                ephemeral=True,
            )
        if self.step == SetupStep.CHANNEL and self.channel:
            permissions = self.channel.permissions_for(self.ctx.guild.me)
            if not (
                permissions.view_channel
                and permissions.send_messages
                and permissions.read_message_history
            ):
                return await interaction.response.send_message(
                    "Grant View Channel, Send Messages and Read Message History there, or choose another channel.",
                    ephemeral=True,
                )
        self.step = NEXT_STEP[self.step]
        self.update_items()
        await interaction.response.edit_message(**self.display())

    async def check_provider(self):
        endpoint = await self.cog.config.custom_openai_endpoint()
        if endpoint != self.settings.get("endpoint"):
            self.models = None
            self.provider_state = ProviderState.UNCONFIGURED
        self.settings["endpoint"] = endpoint
        self.default_model = await self.cog.config.default_model()
        self.settings["model"] = await self.cog.config.guild(self.ctx.guild).model()
        if endpoint == "codex":
            return bool((await load_chatgpt_credentials(self.cog.bot)).get("refresh"))
        return await get_llm_provider(self.cog.services) is not None

    async def verify_existing_provider(self):
        revision = self.provider_revision
        try:
            await self.check_provider()
            provider = await get_llm_provider(self.cog.services)
            if provider is None:
                raise ValueError("Provider unavailable")
            models = await asyncio.wait_for(provider.list_models(), timeout=20)
        # Provider plugins can raise arbitrary errors during setup.
        except Exception as error:  # noqa: BLE001
            log.warning(
                "Configured provider verification failed (%s).", type(error).__name__
            )
            if not self.is_finished() and self.provider_revision == revision:
                endpoint = self.settings.get("endpoint")
                active = (
                    "codex"
                    if endpoint == "codex"
                    else get_openai_compat_kind(endpoint).value
                )
                self.provider_choice = (
                    active
                    if active in {"openai", "openrouter", "codex", "custom"}
                    else "openai"
                )
                self.provider_state = ProviderState.FAILED
                if isinstance(error, AuthenticationError):
                    self.provider_error = "Authentication failed. Check your credentials and Red's logs, or enter an API key."
                elif isinstance(
                    error, (APIConnectionError, APITimeoutError, asyncio.TimeoutError)
                ):
                    self.provider_error = "Couldn't reach the provider. Check the endpoint and Red's logs, then retry."
                else:
                    self.provider_error = (
                        "Check Red's logs, then retry or enter an API key."
                    )
                self.retry_available = True
            return
        if not self.is_finished() and self.provider_revision == revision:
            # An existing provider may not publish a model list. Keep its
            # configured model available without asking the owner to retype it.
            endpoint = self.settings.get("endpoint")
            active = (
                "codex"
                if endpoint == "codex"
                else get_openai_compat_kind(endpoint).value
            )
            self.provider_choice = (
                active
                if active in {"openai", "openrouter", "codex", "custom"}
                else "openai"
            )
            self.models = models or None
            self.provider_state = ProviderState.VERIFIED
            self.provider_error = None
            self.retry_available = False

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Choose a channel to chat in",
        channel_types=[
            discord.ChannelType.text,
            discord.ChannelType.news,
        ],
    )
    async def choose_channel(self, interaction, select):
        channel = self.ctx.guild.get_channel(select.values[0].id)
        if channel is None:
            return await interaction.response.send_message(
                "I can't find that channel. Choose another.",
                ephemeral=True,
            )
        permissions = channel.permissions_for(self.ctx.guild.me)
        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.read_message_history
        ):
            return await interaction.response.send_message(
                "Grant View Channel, Send Messages and Read Message History, then try again.",
                ephemeral=True,
            )
        config = self.cog.config.guild(self.ctx.guild)
        if not self.settings.get("channels_whitelist"):
            saved_chance = await config.get_raw("reply_percent", default=None)
            saved_mentions = await config.get_raw(
                "reply_to_mentions_replies", default=None
            )
            if saved_chance is None and saved_mentions is None:
                await config.reply_percent.set(0.0)
                await config.reply_to_mentions_replies.set(True)
                self.settings["reply_percent"] = 0.0
                self.settings["reply_to_mentions_replies"] = True
                self.chance = 0.0
                for option in self.choose_chance.options:
                    option.default = option.value == "0"
        async with config.channels_whitelist() as channels:
            if (
                self.added_channel_id is not None
                and self.added_channel_id != channel.id
            ):
                if self.added_channel_id in channels:
                    channels.remove(self.added_channel_id)
                self.added_channel_id = None
            if channel.id not in channels:
                channels.append(channel.id)
                self.added_channel_id = channel.id
            self.settings["channels_whitelist"] = list(channels)
        self.channel = channel
        if hasattr(select, "default_values"):
            select.default_values = [channel]
        await interaction.response.edit_message(**self.display())

    @discord.ui.select(
        placeholder="Reply frequency (optional)",
        options=[
            discord.SelectOption(
                label="Only when mentioned",
                value="0",
            ),
            discord.SelectOption(
                label="1%",
                value="0.01",
            ),
            discord.SelectOption(
                label="10%",
                value="0.1",
            ),
            discord.SelectOption(
                label="50%",
                value="0.5",
            ),
            discord.SelectOption(
                label="100%",
                value="1",
            ),
        ],
    )
    async def choose_chance(self, interaction, select):
        self.chance = float(select.values[0])
        config = self.cog.config.guild(self.ctx.guild)
        await config.reply_percent.set(self.chance)
        self.settings["reply_percent"] = self.chance
        if self.chance == 0:
            await config.reply_to_mentions_replies.set(True)
        for option in select.options:
            option.default = option.value == select.values[0]
        await interaction.response.edit_message(**self.display())

    @discord.ui.select(
        placeholder="Personality (optional)",
        options=[
            discord.SelectOption(
                label="Cynical",
                value="cynical",
            ),
            discord.SelectOption(
                label="Neutral",
                value="neutral",
            ),
            discord.SelectOption(
                label="Tsundere",
                value="tsundere",
            ),
        ],
    )
    async def choose_persona(self, interaction, select):
        selected = select.values[0]
        if selected == "previous":
            prompt = self.original_guild_prompt
            effective = (
                prompt
                or self.settings.get("global_prompt")
                or DEFAULT_PRESETS["cynical"]
            )
            self.persona = next(
                (name for name, value in DEFAULT_PRESETS.items() if value == effective),
                None,
            )
            select.options = [
                option for option in select.options if option.value != "previous"
            ]
        else:
            self.persona = selected
            prompt = DEFAULT_PRESETS[selected]
            if not any(option.value == "previous" for option in select.options):
                select.add_option(
                    label="Previous personality",
                    value="previous",
                )
        await self.cog.config.guild(self.ctx.guild).custom_text_prompt.set(prompt)
        self.settings["custom_text_prompt"] = prompt
        self.cog.services.override_prompt_start_time[self.ctx.guild.id] = (
            interaction.created_at
        )
        for option in select.options:
            option.default = option.value == self.persona
        await interaction.response.edit_message(**self.display())

    @discord.ui.button(
        label="Images: Off",
        style=discord.ButtonStyle.secondary,
    )
    async def toggle_images(self, interaction, button):
        enabled = not self.settings.get("scan_images", False)
        await self.cog.config.guild(self.ctx.guild).scan_images.set(enabled)
        self.settings["scan_images"] = enabled
        self.update_items()
        await interaction.response.edit_message(**self.display())

    @discord.ui.button(
        label="Tools: Off",
        style=discord.ButtonStyle.secondary,
    )
    async def toggle_tools(self, interaction, button):
        enabled = not self.settings.get("function_calling", False)
        await self.cog.config.guild(self.ctx.guild).function_calling.set(enabled)
        self.settings["function_calling"] = enabled
        self.update_items()
        await interaction.response.edit_message(**self.display())

    async def _finish(self, interaction, title: str):
        self.stop()
        prefix = self.ctx.clean_prefix
        if self.settings.get("optin_by_default", False):
            message = f"Members are opted in by default on this server. They can opt out with `{prefix}aiuser optout`."
        else:
            message = f"Each member must opt in before the bot can reply using their messages: `{prefix}aiuser optin`."
        message += (
            "\n"
            + "Opt-in lets the bot send users messages to the external third-party LLM provider across its servers."
        )
        if self.provider_state not in (
            ProviderState.CONFIGURED,
            ProviderState.VERIFIED,
        ):
            message += " Configure a provider before chatting."
        embed = discord.Embed(
            title=title,
            description=message,
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"To opt out: {prefix}aiuser optout")
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    @discord.ui.button(
        label="Done",
        style=discord.ButtonStyle.primary,
    )
    async def finish(self, interaction, button):
        await self._finish(interaction, "Setup complete")

    @discord.ui.button(
        label="Exit",
        style=discord.ButtonStyle.secondary,
    )
    async def skip(self, interaction, button):
        await self._finish(interaction, "Setup Saved")

    async def on_timeout(self):
        self.timed_out = True
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    content=f"Setup timed out. Changes are saved. Run `{self.ctx.clean_prefix}aiuser setup` to try again.",
                    view=self,
                )
            except discord.HTTPException:
                pass
