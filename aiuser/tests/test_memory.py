from types import SimpleNamespace

import pytest
import pytest_asyncio

from aiuser.context.memory import fetch_relevant_memory
from aiuser.providers.vectorstore import VectorStore
from aiuser.providers.vectorstore.schema import ensure_sqlite_db


@pytest_asyncio.fixture
async def repo(tmp_path):
    repository = VectorStore(cog_data_path=tmp_path)
    await ensure_sqlite_db(str(repository.db_path))
    return repository


@pytest.fixture
def ctx():
    return SimpleNamespace(
        guild=SimpleNamespace(id=123),
        author=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
    )


@pytest.mark.asyncio
async def test_fetch_relevant_success(repo, ctx):
    expected_text = "I saw a red fox."
    await repo.upsert(123, "red_fox", expected_text)
    await repo.upsert(123, "blue_sun", "Blue sun winks.")
    await repo.upsert(234, "scarlet_echo", "Scarlet echo giggles.")

    out = await fetch_relevant_memory(ctx, repo, "red", threshold=0.2)
    assert out is not None
    assert expected_text in out


@pytest.mark.asyncio
async def test_fetch_relevant_no_match(repo, ctx):
    await repo.upsert(123, "bouncy_muffin", "Bouncy muffin sings.")

    # use a very high threshold so the existing similarity will be below it
    out = await fetch_relevant_memory(ctx, repo, "Toying", threshold=0.99)
    assert out is None


@pytest.mark.asyncio
async def test_fetch_relevant_empty_query(repo, ctx):
    out = await fetch_relevant_memory(ctx, repo, "   ", threshold=1.0)
    assert out is None


@pytest.mark.asyncio
async def test_fetch_relevant_success_with_default_threshold(repo, ctx):
    expected_text = "The fox naps near the red mailbox."
    await repo.upsert(123, "red_mailbox", expected_text)

    out = await fetch_relevant_memory(ctx, repo, "The fox naps near the red mailbox.")
    assert out is not None
    assert expected_text in out


@pytest.mark.asyncio
async def test_fetch_relevant_empty_repository(repo, ctx):
    out = await fetch_relevant_memory(ctx, repo, "anything useful")
    assert out is None
