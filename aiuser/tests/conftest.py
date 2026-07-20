"""
Pytest fixtures for aiuser tests using dpytest.
"""

import json
import os

import discord
import discord.ext.commands as commands
import discord.ext.test as dpytest
import pytest
import pytest_asyncio
from discord.ext.test import backend
from openai import AsyncOpenAI
from redbot.core import Config

from openai.types.chat import ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_message_tool_call import Function

from aiuser.config.defaults import (
    DEFAULT_CHANNEL,
    DEFAULT_GLOBAL,
    DEFAULT_GUILD,
    DEFAULT_MEMBER,
    DEFAULT_ROLE,
)
from aiuser.context.conversation import Conversation
from aiuser.providers.llm.base import ChatStepResult, LLMProvider


def get_openrouter_api_key():
    """Get OpenRouter API key from redbot settings or environment."""
    settings_path = os.path.join(
        os.path.dirname(__file__), "..", "..", ".redbot-data", "core", "settings.json"
    )
    try:
        with open(settings_path) as f:
            settings = json.load(f)
        tokens = settings["0"]["SHARED_API_TOKENS"]
        if "openrouter" in tokens:
            return tokens["openrouter"]["api_key"].rstrip("\"\\'")
    except (FileNotFoundError, KeyError):
        pass
    return os.environ.get("OPENROUTER_API_KEY")


API_KEY = get_openrouter_api_key()
API_BASE = "https://openrouter.ai/api/v1"


@pytest.fixture
def openai_client():
    """Async OpenAI client configured for OpenRouter."""
    if not API_KEY:
        pytest.skip("OpenRouter API key not available")
    headers = {
        "HTTP-Referer": "https://aiuser.zhao.gg",
        "X-OpenRouter-Title": "aiuser",
    }
    return AsyncOpenAI(api_key=API_KEY, base_url=API_BASE, default_headers=headers)


@pytest.fixture(autouse=True)
def fix_dpytest_history_order(monkeypatch):
    """
    Fix dpytest's channel.history() ordering bug.
    """
    from discord.ext.test import backend as dpytest_backend

    original_logs_from = dpytest_backend.FakeHttp.logs_from

    async def patched_logs_from(
        self, channel_id, limit, before=None, after=None, around=None
    ):
        result = await original_logs_from(
            self, channel_id, limit, before, after, around
        )
        # Reverse to return newest-first (Discord's default behavior)
        # The original returns oldest-first which is incorrect
        return list(reversed(result))

    monkeypatch.setattr(dpytest_backend.FakeHttp, "logs_from", patched_logs_from)


@pytest_asyncio.fixture
async def bot():
    """Create a real discord.py bot configured with dpytest, with Red-bot methods mocked."""
    from unittest.mock import AsyncMock

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    b = commands.Bot(command_prefix="!", intents=intents)
    await b._async_setup_hook()
    dpytest.configure(b)

    # Mock Red-bot specific methods
    b.owner_ids.add(dpytest.get_config().members[0].id)
    b.allowed_by_whitelist_blacklist = AsyncMock(return_value=True)
    b.get_embed_color = AsyncMock(return_value=discord.Color.blue())

    yield b
    await dpytest.empty_queue()


@pytest_asyncio.fixture
async def redbot_config():
    """Create a real Redbot Config with aiuser defaults registered."""
    config = Config.get_conf(None, identifier=754070999, cog_name="AIUserTest")
    config.register_member(**DEFAULT_MEMBER)
    config.register_role(**DEFAULT_ROLE)
    config.register_channel(**DEFAULT_CHANNEL)
    config.register_guild(**DEFAULT_GUILD)
    config.register_global(**DEFAULT_GLOBAL)
    config.register_guild(model="openai/gpt-4.1-nano")

    yield config
    # Cleanup
    await config.clear_all()


@pytest.fixture
def test_guild(bot):
    """Return the first guild from dpytest config."""
    return dpytest.get_config().guilds[0]


@pytest.fixture
def test_channel(bot):
    """Return the first channel from dpytest config."""
    return dpytest.get_config().channels[0]


@pytest.fixture
def test_member(bot):
    """Return the first member from dpytest config."""
    return dpytest.get_config().members[0]


@pytest_asyncio.fixture
async def mock_services(bot, redbot_config, test_guild):
    """A real AIUserServices wired to the test bot and config."""
    from unittest.mock import MagicMock

    from aiuser.config.resolver import ScopedConfigResolver
    from aiuser.consent import ConsentService
    from aiuser.core.services import AIUserServices, GuildIgnoreRegexCache
    from aiuser.utils.cache import Cache

    consent = ConsentService(bot, redbot_config)
    await consent.load()
    ignore_regex_cache = GuildIgnoreRegexCache(redbot_config)
    await ignore_regex_cache.load_all()

    services = AIUserServices(
        bot=bot,
        config=redbot_config,
        consent=consent,
        resolver=ScopedConfigResolver(redbot_config),
        ignore_regex_cache=ignore_regex_cache,
        memories=None,  # skip memory retriever
        compaction_store=None,
        compaction_manager=None,
        context_cache=Cache(limit=200),
        cog=MagicMock(),
    )

    # Opt-in by default for the test guild
    await services.config.guild(test_guild).optin_by_default.set(True)

    return services


@pytest_asyncio.fixture
async def build_conversation(bot, mock_services, test_channel, test_member):
    """
    Factory fixture that builds a Conversation via ConversationAssembler
    with real dpytest Discord objects and real services.
    """
    from aiuser.context.assembler import ConversationAssembler

    async def _create(
        init_message: discord.Message = None,
        prompt: str = None,
    ) -> Conversation:
        """
        Prompt should only be provided when init_message is None.
        """
        if init_message:
            ctx = await bot.get_context(init_message)
        else:
            message = backend.make_message("test content", test_member, test_channel)
            ctx = await bot.get_context(message)

        assembler = ConversationAssembler(mock_services, ctx)
        if prompt:
            return await assembler.build_prompt_only(prompt)
        return await assembler.build()

    return _create


class FakeLLMProvider(LLMProvider):
    """Scripted LLMProvider adapter: returns the given steps in order."""

    def __init__(self, steps):
        super().__init__(config=None)
        self.steps = list(steps)
        self.calls = []  # (model, messages, kwargs) per create_chat_step

    async def list_models(self):
        return ["fake-model"]

    async def create_chat_step(self, model, messages, kwargs):
        self.calls.append((model, list(messages), dict(kwargs)))
        return self.steps.pop(0)


def text_step(content, finish_reason="stop"):
    return ChatStepResult(content=content, tool_calls=[], finish_reason=finish_reason)


def tool_call_step(name, arguments, call_id="call_1"):
    tool_call = ChatCompletionMessageToolCall(
        id=call_id,
        type="function",
        function=Function(name=name, arguments=arguments),
    )
    return ChatStepResult(
        content=None, tool_calls=[tool_call], finish_reason="tool_calls"
    )


@pytest.fixture
def fake_llm(monkeypatch):
    """Install a FakeLLMProvider behind the get_llm_provider seam."""

    def _install(*steps):
        fake = FakeLLMProvider(steps)

        async def fake_get(services):
            return fake

        monkeypatch.setattr("aiuser.response.pipeline.get_llm_provider", fake_get)
        return fake

    return _install


@pytest.fixture
def mock_create_response(monkeypatch):
    from contextlib import asynccontextmanager

    import aiuser.response.response as response_module

    original_create_response = response_module.create_response

    # Create a no-op async context manager specifically for this patch
    @asynccontextmanager
    async def noop_typing():
        yield

    async def patched_create_response(
        services, ctx, conversation=None, history_anchor=None
    ):
        from aiuser.core.reply_queue import get_or_create_channel_reply_state
        from unittest.mock import patch

        get_or_create_channel_reply_state(services, ctx.channel.id)
        with patch("discord.TextChannel.typing") as mock_typing:
            mock_typing.return_value = noop_typing()
            return await original_create_response(
                services, ctx, conversation, history_anchor
            )

    monkeypatch.setattr(response_module, "create_response", patched_create_response)
    return patched_create_response


def pytest_sessionfinish(session, exitstatus):
    """Clean up dpytest temp files after all tests."""
    import glob

    fileList = glob.glob("./dpytest_*.dat")
    for filePath in fileList:
        try:
            os.remove(filePath)
        except Exception:
            print("Error while deleting file:", filePath)


def find_message_index(result, content_substring):
    """Find the index of a message containing the given substring."""
    for i, m in enumerate(result):
        if content_substring in str(m.get("content", "")):
            return i
    return -1


def find_system_prompt_index(result):
    """Find the index of the system prompt (contains persona/bot instructions)."""
    for i, m in enumerate(result):
        if m["role"] == "system" and "You are" in str(
            m.get("content", "")
        ):  # hack for checking system prompt
            return i
    return -1
