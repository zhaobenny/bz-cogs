from types import SimpleNamespace

import pytest

pytest.importorskip("lancedb")

from aiuser.context.memory.retriever import MemoryRetriever
from aiuser.utils.vectorstore.repository import Repository


@pytest.fixture
def repo(tmp_path):
    repository = Repository(cog_data_path=tmp_path)
    return repository


@pytest.mark.asyncio
async def test_fetch_relevant_success(repo):
    expected_text = "I saw a red fox."
    await repo.upsert(123, "red_fox", expected_text, 1)
    await repo.upsert(123, "blue_sun", "Blue sun winks.", 2)
    await repo.upsert(234, "scarlet_echo", "Scarlet echo giggles.", 2)

    expected_text = "I saw a red fox."

    ctx = SimpleNamespace(guild=SimpleNamespace(id=123))
    retriever = MemoryRetriever(repo.cog_data_path, ctx)

    out = await retriever.fetch_relevant("red", threshold=10.0)
    assert out is not None
    assert expected_text in out


@pytest.mark.asyncio
async def test_fetch_relevant_no_match(repo):
    await repo.upsert(123, "bouncy_muffin", "Bouncy muffin sings.", 1)

    ctx = SimpleNamespace(guild=SimpleNamespace(id=123))
    retriever = MemoryRetriever(repo.cog_data_path, ctx)

    # use a very small threshold so the existing distance will be above it
    out = await retriever.fetch_relevant("Toying", threshold=1e-6)
    assert out is None


@pytest.mark.asyncio
async def test_fetch_relevant_empty_query(repo):
    ctx = SimpleNamespace(guild=SimpleNamespace(id=123))
    retriever = MemoryRetriever(repo.cog_data_path, ctx)
    out = await retriever.fetch_relevant("   ", threshold=1.0)
    assert out is None
