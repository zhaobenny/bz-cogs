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


@pytest.mark.asyncio
async def test_upsert_with_last_compacted_message_id(compaction_store: CompactionStore):
    guild_id = 123
    channel_id = 456
    summary = "Summary with message ID."
    msg_id = 999888777

    await compaction_store.upsert_summary(guild_id, channel_id, summary, msg_id)

    retrieved_summary = await compaction_store.get_summary(guild_id, channel_id)
    assert retrieved_summary == summary

    retrieved_id = await compaction_store.get_last_compacted_message_id(
        guild_id, channel_id
    )
    assert retrieved_id == msg_id


@pytest.mark.asyncio
async def test_get_last_compacted_message_id_nonexistent(
    compaction_store: CompactionStore,
):
    retrieved = await compaction_store.get_last_compacted_message_id(999, 999)
    assert retrieved is None


@pytest.mark.asyncio
async def test_upsert_updates_last_compacted_message_id(
    compaction_store: CompactionStore,
):
    guild_id = 123
    channel_id = 456

    await compaction_store.upsert_summary(guild_id, channel_id, "First", 100)
    await compaction_store.upsert_summary(guild_id, channel_id, "Second", 200)

    retrieved_id = await compaction_store.get_last_compacted_message_id(
        guild_id, channel_id
    )
    assert retrieved_id == 200

    retrieved_summary = await compaction_store.get_summary(guild_id, channel_id)
    assert retrieved_summary == "Second"
