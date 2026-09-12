from __future__ import annotations

import gkeepapi
import pytest
from click.testing import CliRunner

from keep_cli import client


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEP_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("KEEP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("KEEP_EMAIL", raising=False)
    monkeypatch.delenv("KEEP_MASTER_TOKEN", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    return tmp_path


@pytest.fixture
def keep(monkeypatch):
    """An offline Keep populated with sample data; network calls are stubbed."""
    k = gkeepapi.Keep()
    todo = k.createLabel("todo")
    work = k.createLabel("work")

    note = k.createNote("Shopping ideas", "buy a hammer\nand nails")
    note.labels.add(todo)

    lst = k.createList("Groceries", [("milk", False), ("eggs", True), ("bread", False)])
    lst.labels.add(todo)
    lst.pinned = True

    archived = k.createNote("Old plan", "archived body")
    archived.archived = True
    archived.labels.add(work)

    trashed = k.createNote("Garbage", "in the bin")
    trashed.trash()

    k.commits = 0

    def fake_commit(keep_obj):
        assert keep_obj is k
        k.commits += 1

    monkeypatch.setattr(client, "open_keep", lambda *a, **kw: k)
    monkeypatch.setattr(client, "commit", fake_commit)
    k.sample = {"note": note, "list": lst, "archived": archived, "trashed": trashed}
    return k


@pytest.fixture
def run():
    runner = CliRunner()

    def _run(*args, **kwargs):
        from keep_cli.cli import main

        return runner.invoke(main, list(args), catch_exceptions=False, **kwargs)

    return _run
