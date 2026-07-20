import pytest
import pytest_asyncio

# ./.venv/bin/python -m pytest aiuser/tests/test_vectorstore.py -q -s

from aiuser.providers.vectorstore import VectorStore
from aiuser.providers.vectorstore.schema import ensure_sqlite_db


@pytest_asyncio.fixture
async def vectorstore(tmp_path):
    vectorstore = VectorStore(cog_data_path=tmp_path)
    await ensure_sqlite_db(str(vectorstore.db_path))
    return vectorstore


@pytest.mark.asyncio
async def test_upsert_and_list(vectorstore: VectorStore):
    n1 = await vectorstore.upsert(123, "red_fox", "I saw a red fox.")
    assert n1 == 1
    n2 = await vectorstore.upsert(123, "blue_sun", "The blue sun winks.")
    assert n2 == 2

    names = await vectorstore.list(123)
    assert names == [(1, "red_fox"), (2, "blue_sun")]

    # test replace
    replaced_id = await vectorstore.upsert(
        123, "red_fox", "I saw a red fox, it was cute."
    )
    assert replaced_id == n1
    names_after = await vectorstore.list(123)
    assert names_after == [(1, "red_fox"), (2, "blue_sun")]
    _, text = await vectorstore.fetch_by_id(1, 123)
    assert text == "I saw a red fox, it was cute."


@pytest.mark.asyncio
async def test_fetch_by_id(vectorstore: VectorStore):
    # ensure entries exist
    await vectorstore.upsert(123, "green_leaf", "A green leaf dances.")
    await vectorstore.upsert(123, "tiny_star", "A tiny star hums.")

    fetched = await vectorstore.fetch_by_id(2, 123)
    assert fetched == ("tiny_star", "A tiny star hums.")


@pytest.mark.asyncio
async def test_search_similar(vectorstore: VectorStore):
    await vectorstore.upsert(123, "purple_rain", "Purple rain laughs.")
    await vectorstore.upsert(123, "orange_moon", "Orange moon naps.")

    res = await vectorstore.search_similar("query", 123, k=2)
    assert len(res) == 2
    assert {r[0] for r in res} == {"purple_rain", "orange_moon"}


@pytest.mark.asyncio
async def test_delete_and_list(vectorstore: VectorStore):
    await vectorstore.upsert(123, "swift_owl", "Swift owl blinks.")
    await vectorstore.upsert(123, "lazy_cat", "Lazy cat snores.")

    ok = await vectorstore.delete(1, 123)
    assert ok is True

    names_after = await vectorstore.list(123)
    assert names_after == [(2, "lazy_cat")]


@pytest.mark.asyncio
async def test_upsert_and_search_with_user_and_channel(vectorstore: VectorStore):
    # Upsert generic memory
    await vectorstore.upsert(123, "global_rule", "Global rule is X.")
    # Upsert user specific memory
    await vectorstore.upsert(123, "user_rule", "User rule is Y.", user="1")
    # Upsert channel specific memory
    await vectorstore.upsert(123, "channel_rule", "Channel rule is Z.", channel="10")
    # Upsert both user and channel memory
    await vectorstore.upsert(
        123, "both_rule", "Both rule is W.", user="2", channel="10"
    )

    # 1. Search with no user/channel -> Should get all 4.
    res_all = await vectorstore.search_similar("rule", 123, k=4)
    assert len(res_all) == 4

    # 2. Search specific to Alice -> Should get global_rule and user_rule
    res_alice = await vectorstore.search_similar("rule", 123, k=4, user="1")
    names_alice = {r[0] for r in res_alice}
    assert "user_rule" in names_alice
    assert "global_rule" in names_alice
    assert "channel_rule" in names_alice
    assert "both_rule" not in names_alice

    # 3. Search specific to channel="general", no user
    res_general = await vectorstore.search_similar("rule", 123, k=4, channel="10")
    names_general = {r[0] for r in res_general}
    assert "global_rule" in names_general
    assert "user_rule" in names_general
    assert "channel_rule" in names_general
    assert "both_rule" in names_general

    # 4. Search specific to Bob in general channel
    res_bob_gen = await vectorstore.search_similar(
        "rule", 123, k=4, user="2", channel="10"
    )
    names_bob_gen = {r[0] for r in res_bob_gen}
    assert "global_rule" in names_bob_gen
    assert "both_rule" in names_bob_gen
    assert "channel_rule" in names_bob_gen
    assert "user_rule" not in names_bob_gen
