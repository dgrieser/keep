import json


def test_list_hides_archived_and_trashed(keep, run):
    result = run("list")
    assert result.exit_code == 0, result.output
    assert "Shopping ideas" in result.output
    assert "Groceries" in result.output
    assert "Old plan" not in result.output
    assert "Garbage" not in result.output


def test_list_pinned_first(keep, run):
    result = run("list")
    lines = result.output.splitlines()
    assert "Groceries" in lines[1]
    assert lines[1].split()[1] == "P--L"


def test_list_archived_and_all(keep, run):
    only = run("list", "--archived")
    assert "Old plan" in only.output and "Groceries" not in only.output
    everything = run("list", "--all")
    assert "Old plan" in everything.output and "Groceries" in everything.output
    assert "Garbage" not in everything.output


def test_list_trashed(keep, run):
    result = run("list", "--trashed")
    assert "Garbage" in result.output
    assert "Groceries" not in result.output


def test_list_search_matches_body(keep, run):
    result = run("list", "--search", "HAMMER")
    assert "Shopping ideas" in result.output
    assert "Groceries" not in result.output


def test_list_filter_label_and_pinned(keep, run):
    result = run("list", "--label", "todo", "--pinned")
    assert "Groceries" in result.output
    assert "Shopping ideas" not in result.output
    result = run("list", "--label", "todo", "--unpinned")
    assert "Shopping ideas" in result.output
    assert "Groceries" not in result.output


def test_list_unknown_label(keep, run):
    result = run("list", "--label", "nope")
    assert result.exit_code == 2
    assert "No label named 'nope'" in result.output


def test_list_color_and_limit(keep, run):
    from gkeepapi.node import ColorValue

    keep.sample["note"].color = ColorValue.Red
    result = run("list", "--color", "red")
    assert "Shopping ideas" in result.output and "Groceries" not in result.output
    result = run("list", "--limit", "1", "--json")
    assert len(json.loads(result.output)) == 1


def test_list_json(keep, run):
    result = run("list", "--json")
    data = json.loads(result.output)
    by_title = {d["title"]: d for d in data}
    assert by_title["Groceries"]["type"] == "list"
    assert by_title["Groceries"]["items"][1] == {"text": "eggs", "checked": True}
    assert by_title["Shopping ideas"]["labels"] == ["todo"]
    assert by_title["Shopping ideas"]["color"] == "white"


def test_list_empty(keep, run):
    result = run("list", "--search", "zzz-nothing")
    assert result.output.strip() == "No notes found."


def test_read_note(keep, run):
    note = keep.sample["note"]
    result = run("read", note.id)
    assert result.exit_code == 0
    assert "Title:    Shopping ideas" in result.output
    assert "buy a hammer\nand nails" in result.output
    assert "Labels:   todo" in result.output


def test_read_list_renders_checkboxes(keep, run):
    result = run("read", keep.sample["list"].id)
    assert "[ ] milk" in result.output
    assert "[x] eggs" in result.output
    assert "Type:     checklist" in result.output


def test_read_by_prefix(keep, run):
    note = keep.sample["note"]
    result = run("read", note.id[: len(note.id) - 3], "--json")
    assert json.loads(result.output)["id"] == note.id


def test_read_unknown(keep, run):
    result = run("read", "does-not-exist")
    assert result.exit_code == 2
    assert "No note found" in result.output


def test_read_ambiguous_prefix(keep, run):
    # All ids share a timestamp-based prefix; use the first character.
    ids = [n.id for n in keep.all()]
    prefix = ids[0][:1]
    assert all(i.startswith(prefix) for i in ids)
    result = run("read", prefix)
    assert result.exit_code == 2
    assert "ambiguous" in result.output
