import pytest

# ./.venv/bin/python -m pytest aiuser/tests/test_vectorstore.py -q -s

from aiuser.utils.vectorstore import VectorStore


@pytest.fixture
def vectorstore(tmp_path):
    vectorstore = VectorStore(cog_data_path=tmp_path)
    return vectorstore


@pytest.mark.asyncio
async def test_upsert_and_list(vectorstore: VectorStore):
    n1 = await vectorstore.upsert(123, "red_fox", "I saw a red fox.", 1)
    assert n1 == 1
    n2 = await vectorstore.upsert(123, "blue_sun", "The blue sun winks.", 2)
    assert n2 == 2

    names = await vectorstore.list(123)
    assert names == [(1, "red_fox"), (2, "blue_sun")]


@pytest.mark.asyncio
async def test_fetch_by_rowid(vectorstore: VectorStore):
    # ensure entries exist
    await vectorstore.upsert(123, "green_leaf", "A green leaf dances.", 1)
    await vectorstore.upsert(123, "tiny_star", "A tiny star hums.", 2)

    fetched = await vectorstore.fetch_by_rowid(2, 123)
    assert fetched == ("tiny_star", "A tiny star hums.")


@pytest.mark.asyncio
async def test_search_similar(vectorstore: VectorStore):
    await vectorstore.upsert(123, "purple_rain", "Purple rain laughs.", 1)
    await vectorstore.upsert(123, "orange_moon", "Orange moon naps.", 2)

    res = await vectorstore.search_similar("query", 123, k=2)
    assert len(res) == 2
    assert {r[0] for r in res} == {"purple_rain", "orange_moon"}


@pytest.mark.asyncio
async def test_delete_and_list(vectorstore: VectorStore):
    await vectorstore.upsert(123, "swift_owl", "Swift owl blinks.", 1)
    await vectorstore.upsert(123, "lazy_cat", "Lazy cat snores.", 2)

    ok = await vectorstore.delete(1, 123)
    assert ok is True

    names_after = await vectorstore.list(123)
    assert names_after == [(1, "lazy_cat")]


@pytest.mark.asyncio
async def test_upsert_and_search_with_user_and_channel(vectorstore: VectorStore):
    # Upsert generic memory
    await vectorstore.upsert(123, "global_rule", "Global rule is X.", 1)
    # Upsert user specific memory
    await vectorstore.upsert(123, "user_rule", "User rule is Y.", 1, user="Alice")
    # Upsert channel specific memory
    await vectorstore.upsert(
        123, "channel_rule", "Channel rule is Z.", 1, channel="general"
    )
    # Upsert both user and channel memory
    await vectorstore.upsert(
        123, "both_rule", "Both rule is W.", 1, user="Bob", channel="general"
    )

    # Searching with no user or channel should return generic memories only
    # 1. Search with no user/channel -> Should get all 4.
    res_all = await vectorstore.search_similar("rule", 123, k=4)
    assert len(res_all) == 4

    # 2. Search specific to Alice -> Should get global_rule and user_rule
    res_alice = await vectorstore.search_similar("rule", 123, k=4, user="Alice")
    names_alice = {r[0] for r in res_alice}
    assert "user_rule" in names_alice
    assert "global_rule" in names_alice
    assert "channel_rule" in names_alice
    assert "both_rule" not in names_alice

    # 3. Search specific to channel="general", no user
    res_general = await vectorstore.search_similar("rule", 123, k=4, channel="general")
    names_general = {r[0] for r in res_general}
    assert "global_rule" in names_general
    assert "user_rule" in names_general
    assert "channel_rule" in names_general
    assert "both_rule" in names_general

    # 4. Search specific to Bob in general channel
    res_bob_gen = await vectorstore.search_similar(
        "rule", 123, k=4, user="Bob", channel="general"
    )
    names_bob_gen = {r[0] for r in res_bob_gen}
    assert "global_rule" in names_bob_gen
    assert "both_rule" in names_bob_gen
    assert "channel_rule" in names_bob_gen
    assert "user_rule" not in names_bob_gen
