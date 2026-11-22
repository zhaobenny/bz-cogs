from aiuser.functions import source_search


def test_search_reads_only_cog_source(tmp_path, monkeypatch):
    package = tmp_path / "aiuser"
    settings = package / "settings"
    settings.mkdir(parents=True)
    (settings / "reply.py").write_text("class ReplySettings:\n    pass\n")

    external = tmp_path / "external.py"
    external.write_text("ReplySettings = 'from a different package'\n")
    (settings / "linked.py").symlink_to(external)
    (settings / "config.json").write_text('{"ReplySettings": "runtime config"}')
    (package / "local.py").write_text("ReplySettings = 'local extra file'\n")

    monkeypatch.setattr(source_search, "_SOURCE_ROOT", package)
    results = source_search.search_source("ReplySettings")

    assert results == [
        {
            "file": "settings/reply.py",
            "start_line": 1,
            "end_line": 2,
            "source": "class ReplySettings:\n    pass",
        }
    ]
