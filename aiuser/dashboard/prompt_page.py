from __future__ import annotations

import json
import pathlib

import discord

from aiuser.dashboard.decorator import dashboard_page
from aiuser.types.abc import MixinMeta
from aiuser.utils.prompt_metrics import (
    get_prompt_metrics,
)

TEMPLATES_PATH = pathlib.Path(__file__).parent / "templates"


async def _prompt_item(
    scope: str,
    name: str,
    value: str,
    model: str,
):
    metrics = await get_prompt_metrics(value, model)
    cost_per_1k_label = (
        f"{metrics.cost_per_1k_label} estimated per 1K uses"
        if metrics.cost_per_1k_label
        else None
    )

    return {
        "scope": scope,
        "name": name,
        "value": value,
        "token_label": metrics.token_label,
        "cost_per_1k_label": cost_per_1k_label,
    }


async def _collect_entity_prompts(
    config_getter,
    entities,
    scope: str,
    model: str,
    prompt_attr: str,
):
    prompts = [
        await _prompt_item(scope, _entity_name(entity), prompt, model)
        for entity in entities
        if (prompt := await getattr(config_getter(entity), prompt_attr)())
    ]
    return prompts


async def _collect_scoped_prompts(
    self: MixinMeta,
    guild: discord.Guild,
    model: str,
    prompt_attr: str,
):
    prompts = []
    guild_prompt = await getattr(self.config.guild(guild), prompt_attr)()
    if guild_prompt:
        prompts.append(await _prompt_item("Server", guild.name, guild_prompt, model))

    entity_groups = (
        (self.config.channel, guild.channels, "Channel"),
        (self.config.role, guild.roles, "Role"),
        (self.config.member, guild.members, "Member"),
    )
    for config_getter, entities, scope in entity_groups:
        prompts.extend(
            await _collect_entity_prompts(
                config_getter,
                entities,
                scope,
                model,
                prompt_attr,
            )
        )
    return prompts


async def _collect_presets(config, guild: discord.Guild, model: str):
    prompts = []
    for name, prompt in _load_presets(await config.guild(guild).presets()).items():
        prompts.append(await _prompt_item("Preset", str(name), str(prompt), model))
    return prompts


async def _collect_random_prompts(config, guild: discord.Guild, model: str):
    prompts = []
    topics = await config.guild(guild).random_messages_prompts()
    for index, prompt in enumerate(topics, start=1):
        prompts.append(await _prompt_item("Topic", f"Topic {index}", prompt, model))
    return prompts


def _metrics_footer(metrics) -> str:
    notes = []
    if metrics.uses_fallback_tokenizer:
        notes.append(f"Tokens count estimated using {metrics.tokenizer_name}")
    if metrics.cost_per_1k_label:
        notes.append("Pricing uses the lowest matching OpenRouter rate")
    return "\n".join(notes)


def _entity_name(entity) -> str:
    return getattr(entity, "display_name", None) or getattr(
        entity, "name", str(entity.id)
    )


def _load_presets(raw_presets: str):
    try:
        presets = json.loads(raw_presets or "{}")
    except json.JSONDecodeError:
        return {}
    return presets if isinstance(presets, dict) else {}


@dashboard_page(
    name="prompt_overview",
    description="Read-only page of configured prompts.",
    methods=("GET",),
    is_owner=True,
)
async def prompt_overview(self: MixinMeta, guild: discord.Guild, **kwargs):
    model = await self.config.guild(guild).model()
    server_prompt = await self.services.resolver.resolve_prompt(guild=guild)

    template_path = TEMPLATES_PATH / "prompt_page.html"
    source = template_path.read_text()

    return {
        "status": 0,
        "web_content": {
            "source": source,
            "metrics_footer": _metrics_footer(
                await get_prompt_metrics(server_prompt, model)
            ),
            "server_prompt": await _prompt_item(
                "Server", guild.name, server_prompt, model
            ),
            "scoped_prompts": await _collect_scoped_prompts(
                self, guild, model, "custom_text_prompt"
            ),
            "presets": await _collect_presets(self.config, guild, model),
            "random_prompts": await _collect_random_prompts(self.config, guild, model),
            "image_preprompts": await _collect_scoped_prompts(
                self, guild, model, "function_calling_image_preprompt"
            ),
        },
    }
