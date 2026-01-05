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

from aiuser.config.defaults import (
    DEFAULT_CHANNEL,
    DEFAULT_GLOBAL,
    DEFAULT_GUILD,
    DEFAULT_MEMBER,
    DEFAULT_ROLE,
)
from aiuser.context.messages import MessagesThread


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
        "X-Title": "aiuser",
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
async def mock_cog(bot, redbot_config, test_guild):
    """
    Create a mock cog with all attributes needed by ThreadSetup and MessagesThread.
    """
    from unittest.mock import MagicMock

    from aiuser.utils.cache import Cache

    cog = MagicMock()
    cog.bot = bot
    cog.config = redbot_config
    cog.ignore_regex = {}  # Dict keyed by guild.id
    cog.override_prompt_start_time = {}  # Dict keyed by guild.id
    cog.db = None  # Skip memory retriever
    cog.cached_tool_calls = Cache(limit=100)

    # Opt-in by default for the test guild
    await cog.config.guild(test_guild).optin_by_default.set(True)

    return cog


@pytest_asyncio.fixture
async def mock_messages_thread(bot, mock_cog, test_channel, test_member):
    """
    Factory fixture to create a MessagesThread using ThreadSetup.create_thread()
    with real dpytest Discord objects and a mock cog.
    """
    from aiuser.context.setup import ThreadSetup

    async def _create(
        init_message: discord.Message = None,
        prompt: str = None,
    ) -> MessagesThread:
        """
        Prompt should only be provided when init_message is None.
        """
        if init_message:
            # Use provided message
            ctx = await bot.get_context(init_message)
        else:
            # Create a new message
            message = backend.make_message("test content", test_member, test_channel)
            ctx = await bot.get_context(message)

        # Use ThreadSetup to create the thread properly
        setup = ThreadSetup(mock_cog, ctx)
        thread = await setup.create_thread(prompt=prompt)

        return thread

    return _create


@pytest.fixture
def mock_create_response(monkeypatch):
    from contextlib import asynccontextmanager

    import aiuser.response.response as response_module

    original_create_response = response_module.create_response

    # Create a no-op async context manager specifically for this patch
    @asynccontextmanager
    async def noop_typing():
        yield

    async def patched_create_response(cog, ctx, messages_list=None):
        from unittest.mock import patch

        with patch("discord.TextChannel.typing") as mock_typing:
            mock_typing.return_value = noop_typing()
            return await original_create_response(cog, ctx, messages_list)

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
