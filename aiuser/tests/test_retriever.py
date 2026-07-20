from types import SimpleNamespace

import pytest
import pytest_asyncio

from aiuser.context.memory.retriever import MemoryRetriever
from aiuser.providers.vectorstore import VectorStore
from aiuser.providers.vectorstore.schema import ensure_sqlite_db


@pytest_asyncio.fixture
async def repo(tmp_path):
    repository = VectorStore(cog_data_path=tmp_path)
    await ensure_sqlite_db(str(repository.db_path))
    return repository


@pytest.mark.asyncio
async def test_fetch_relevant_success(repo):
    expected_text = "I saw a red fox."
    await repo.upsert(123, "red_fox", expected_text)
    await repo.upsert(123, "blue_sun", "Blue sun winks.")
    await repo.upsert(234, "scarlet_echo", "Scarlet echo giggles.")

    expected_text = "I saw a red fox."

    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=123),
        author=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
    )
    retriever = MemoryRetriever(ctx, repo)

    out = await retriever.fetch_relevant("red", threshold=0.2)
    assert out is not None
    assert expected_text in out


@pytest.mark.asyncio
async def test_fetch_relevant_no_match(repo):
    await repo.upsert(123, "bouncy_muffin", "Bouncy muffin sings.")

    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=123),
        author=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
    )
    retriever = MemoryRetriever(ctx, repo)

    # use a very high threshold so the existing similarity will be below it
    out = await retriever.fetch_relevant("Toying", threshold=0.99)
    assert out is None


@pytest.mark.asyncio
async def test_fetch_relevant_empty_query(repo):
    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=123),
        author=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
    )
    retriever = MemoryRetriever(ctx, repo)
    out = await retriever.fetch_relevant("   ", threshold=1.0)
    assert out is None


@pytest.mark.asyncio
async def test_fetch_relevant_success_with_default_threshold(repo):
    expected_text = "The fox naps near the red mailbox."
    await repo.upsert(123, "red_mailbox", expected_text)

    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=123),
        author=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
    )
    retriever = MemoryRetriever(ctx, repo)

    out = await retriever.fetch_relevant("The fox naps near the red mailbox.")
    assert out is not None
    assert expected_text in out


@pytest.mark.asyncio
async def test_fetch_relevant_empty_repository(repo):
    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=123),
        author=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
    )
    retriever = MemoryRetriever(ctx, repo)

    out = await retriever.fetch_relevant("anything useful")
    assert out is None
