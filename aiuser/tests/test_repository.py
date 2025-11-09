import pytest

# ./.venv/bin/python -m pytest aiuser/tests/test_repository.py -q -s

pytest.importorskip("lancedb")

from aiuser.utils.vectorstore.repository import Repository


@pytest.fixture
def repo(tmp_path):
    repository = Repository(cog_data_path=tmp_path)
    return repository


@pytest.mark.asyncio
async def test_upsert_and_list(repo: Repository):
    n1 = await repo.upsert(123, "note1", "hello world", 1)
    assert n1 == 1
    n2 = await repo.upsert(123, "note2", "another", 2)
    assert n2 == 2

    names = await repo.list(123)
    assert names == [(1, "note1"), (2, "note2")]


@pytest.mark.asyncio
async def test_fetch_by_rowid(repo: Repository):
    # ensure entries exist
    await repo.upsert(123, "note1", "hello world", 1)
    await repo.upsert(123, "note2", "another", 2)

    fetched = await repo.fetch_by_rowid(2, 123)
    assert fetched == ("note2", "another")


@pytest.mark.asyncio
async def test_search_similar(repo: Repository):
    await repo.upsert(123, "note1", "hello world", 1)
    await repo.upsert(123, "note2", "another", 2)

    res = await repo.search_similar("query", 123, k=2)
    assert len(res) == 2
    assert {r[0] for r in res} == {"note1", "note2"}


@pytest.mark.asyncio
async def test_delete_and_list(repo: Repository):
    await repo.upsert(123, "note1", "hello world", 1)
    await repo.upsert(123, "note2", "another", 2)

    ok = await repo.delete(1, 123)
    assert ok is True

    names_after = await repo.list(123)
    assert names_after == [(1, "note2")]
