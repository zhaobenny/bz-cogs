import pytest
from pathlib import Path

from aiuser.utils.compaction.store import CompactionStore


@pytest.fixture
def compaction_store(tmp_path: Path):
    store = CompactionStore(tmp_path)
    return store


@pytest.mark.asyncio
async def test_upsert_and_get_summary(compaction_store: CompactionStore):
    guild_id = 123
    channel_id = 456
    summary = "This is a test summary."

    await compaction_store.upsert_summary(guild_id, channel_id, summary)

    retrieved = await compaction_store.get_summary(guild_id, channel_id)
    assert retrieved == summary


@pytest.mark.asyncio
async def test_update_summary(compaction_store: CompactionStore):
    guild_id = 123
    channel_id = 456
    summary1 = "First summary."
    summary2 = "Updated summary."

    await compaction_store.upsert_summary(guild_id, channel_id, summary1)
    await compaction_store.upsert_summary(guild_id, channel_id, summary2)

    retrieved = await compaction_store.get_summary(guild_id, channel_id)
    assert retrieved == summary2


@pytest.mark.asyncio
async def test_get_nonexistent_summary(compaction_store: CompactionStore):
    retrieved = await compaction_store.get_summary(999, 999)
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_summary(compaction_store: CompactionStore):
    guild_id = 123
    channel_id = 456
    summary = "This is a test summary."

    await compaction_store.upsert_summary(guild_id, channel_id, summary)
    await compaction_store.delete_summary(guild_id, channel_id)

    retrieved = await compaction_store.get_summary(guild_id, channel_id)
    assert retrieved is None
