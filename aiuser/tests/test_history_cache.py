
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from datetime import datetime
from aiuser.context.history.builder import HistoryBuilder
from aiuser.context.entry import MessageEntry
from aiuser.utils.cache import Cache

@pytest.fixture
def mock_cog():
    cog = SimpleNamespace()
    cog.config = MagicMock()
    cog.tool_call_cache = Cache(limit=100)
    cog.cached_messages = Cache(limit=100)
    cog.bot = MagicMock()
    cog.bot.user.id = 12345
    return cog

@pytest.fixture
def mock_messages_thread(mock_cog):
    thread = MagicMock()
    thread.cog = mock_cog
    thread.config = mock_cog.config
    thread.bot = mock_cog.bot
    thread.tokens = 0
    thread.token_limit = 1000
    thread.add_msg = AsyncMock()
    thread.add_entries = AsyncMock()
    return thread

@pytest.mark.asyncio
async def test_history_builder_injects_tool_calls(mock_cog, mock_messages_thread):
    # Setup messages
    msg1 = MagicMock()
    msg1.id = 1001
    msg1.created_at = datetime.now()
    msg1.author.id = 12345 # Bot

    msg2 = MagicMock()
    msg2.id = 1002
    msg2.created_at = datetime.now()
    msg2.author.id = 99999 # User (Boundary message)

    # Mock cached tool calls for msg1 (the bot response)
    tool_entry = MessageEntry("tool", "result", tool_call_id="call_1")
    mock_cog.tool_call_cache[msg1.id] = [tool_entry]

    # Setup Builder
    builder = HistoryBuilder(mock_messages_thread)

    # Mock _is_valid_time_gap to always return True
    with patch.object(builder, "_is_valid_time_gap", return_value=True):
        # Run process_past_messages
        # past_messages are Newest -> Oldest
        # [msg1, msg2]
        # Only msg1 will be added, msg2 is for gap check.
        await builder._process_past_messages([msg1, msg2], 60)

    # Assertions
    # msg1 processed first
    # 1. add_msg(msg1)
    # 2. add_entries([tool_entry])

    assert mock_messages_thread.add_msg.call_count == 1
    assert mock_messages_thread.add_entries.call_count == 1

    # Check call args
    mock_messages_thread.add_entries.assert_called_with([tool_entry])

    # Verify order of calls
    calls = mock_messages_thread.method_calls
    relevant_calls = [c for c in calls if c[0] in ['add_msg', 'add_entries']]

    # Expect: add_msg(msg1) THEN add_entries(tools)
    assert relevant_calls[0][0] == 'add_msg'
    assert relevant_calls[0][1][0] == msg1
    assert relevant_calls[1][0] == 'add_entries'
    assert relevant_calls[1][1][0] == [tool_entry]
