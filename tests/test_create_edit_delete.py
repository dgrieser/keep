import json

from gkeepapi import node as gnode


def test_create_text_note(keep, run):
    result = run("create", "Title here", "--text", "some body", "--label", "newlabel", "--pin")
    assert result.exit_code == 0, result.output
    new_id = result.output.strip()
    note = keep.get(new_id)
    assert isinstance(note, gnode.Note)
    assert note.title == "Title here"
    assert note.text == "some body"
    assert note.pinned is True
    assert [lb.name for lb in note.labels.all()] == ["newlabel"]
    assert keep.findLabel("newlabel") is not None
    assert keep.commits == 1


def test_create_from_stdin_and_color(keep, run):
    result = run("create", "Piped", "--stdin", "--color", "Teal", input="line1\nline2\n")
    note = keep.get(result.output.strip())
    assert note.text == "line1\nline2\n"
    assert note.color == gnode.ColorValue.Teal


def test_create_checklist(keep, run):
    result = run("create", "Todo", "-i", "one", "-i", "two", "--checked", "done", "--archive")
    note = keep.get(result.output.strip())
    assert isinstance(note, gnode.List)
    assert [(i.text, i.checked) for i in note.items] == [
        ("one", False),
        ("two", False),
        ("done", True),
    ]
    assert note.archived is True


def test_create_requires_content(keep, run):
    result = run("create")
    assert result.exit_code == 2
    assert "Nothing to create" in result.output
    assert keep.commits == 0


def test_create_rejects_item_with_text(keep, run):
    result = run("create", "x", "--item", "a", "--text", "b")
    assert result.exit_code == 2


def test_edit_title_text_flags(keep, run):
    note = keep.sample["note"]
    result = run(
        "edit",
        note.id,
        "--title",
        "New title",
        "--text",
        "replaced",
        "--unpin",
        "--archive",
        "--color",
        "green",
        "--add-label",
        "work",
        "--remove-label",
        "todo",
    )
    assert result.exit_code == 0, result.output
    assert note.title == "New title"
    assert note.text == "replaced"
    assert note.archived is True
    assert note.color == gnode.ColorValue.Green
    assert [lb.name for lb in note.labels.all()] == ["work"]
    assert keep.commits == 1


def test_edit_append(keep, run):
    note = keep.sample["note"]
    run("edit", note.id, "--append", "third line")
    assert note.text == "buy a hammer\nand nails\nthird line"


def test_edit_stdin(keep, run):
    note = keep.sample["note"]
    run("edit", note.id, "--stdin", input="from stdin\n")
    assert note.text == "from stdin"


def test_edit_text_on_list_rejected(keep, run):
    result = run("edit", keep.sample["list"].id, "--text", "nope")
    assert result.exit_code == 2
    assert "checklist" in result.output
    assert keep.commits == 0


def test_edit_items_on_note_rejected(keep, run):
    result = run("edit", keep.sample["note"].id, "--add-item", "nope")
    assert result.exit_code == 2
    assert "not a checklist" in result.output


def test_edit_checklist_items(keep, run):
    lst = keep.sample["list"]
    result = run(
        "edit",
        lst.id,
        "--check",
        "1",
        "--uncheck",
        "eggs",
        "--remove-item",
        "bread",
        "--add-item",
        "butter",
    )
    assert result.exit_code == 0, result.output
    assert [(i.text, i.checked) for i in lst.items] == [
        ("milk", True),
        ("eggs", False),
        ("butter", False),
    ]


def test_edit_item_selector_errors(keep, run):
    lst = keep.sample["list"]
    assert run("edit", lst.id, "--check", "9").exit_code == 2
    assert run("edit", lst.id, "--check", "caviar").exit_code == 2


def test_edit_mutually_exclusive_body_options(keep, run):
    result = run("edit", keep.sample["note"].id, "--text", "a", "--append", "b")
    assert result.exit_code == 2


def test_edit_editor_note(keep, run, monkeypatch):
    import click

    note = keep.sample["note"]
    captured = {}

    def fake_edit(text, **kwargs):
        captured["buffer"] = text
        return "# comment\nEdited title\n\nnew body\nsecond\n"

    monkeypatch.setattr(click, "edit", fake_edit)
    result = run("edit", note.id)
    assert result.exit_code == 0, result.output
    assert "Shopping ideas" in captured["buffer"]
    assert note.title == "Edited title"
    assert note.text == "new body\nsecond"


def test_edit_editor_list(keep, run, monkeypatch):
    import click

    lst = keep.sample["list"]
    monkeypatch.setattr(
        click, "edit", lambda text, **kw: "Groceries\n\n[x] bread\n[ ] milk\n[ ] cheese\n"
    )
    result = run("edit", lst.id, "--editor")
    assert result.exit_code == 0, result.output
    assert [(i.text, i.checked) for i in lst.items] == [
        ("bread", True),
        ("milk", False),
        ("cheese", False),
    ]


def test_edit_editor_aborted(keep, run, monkeypatch):
    import click

    monkeypatch.setattr(click, "edit", lambda text, **kw: None)
    result = run("edit", keep.sample["note"].id)
    assert result.exit_code == 0
    assert "aborted" in result.output.lower()
    assert keep.commits == 0


def test_delete_trashes_with_confirmation(keep, run):
    note = keep.sample["note"]
    result = run("delete", note.id, input="y\n")
    assert result.exit_code == 0, result.output
    assert note.trashed is True
    assert f"Trashed {note.id}" in result.output


def test_delete_declined(keep, run):
    note = keep.sample["note"]
    result = run("delete", note.id, input="n\n")
    assert result.exit_code == 1
    assert note.trashed is False
    assert keep.commits == 0


def test_delete_permanent_yes(keep, run):
    note = keep.sample["note"]
    lst = keep.sample["list"]
    result = run("delete", "--permanent", "-y", note.id, lst.id)
    assert result.exit_code == 0
    assert note.deleted and lst.deleted
    assert keep.commits == 1


def test_restore(keep, run):
    trashed = keep.sample["trashed"]
    result = run("restore", trashed.id)
    assert result.exit_code == 0
    assert trashed.trashed is False
    result = run("restore", keep.sample["note"].id)
    assert result.exit_code == 2


def test_json_roundtrip_after_edit(keep, run):
    lst = keep.sample["list"]
    run("edit", lst.id, "--check", "milk")
    data = json.loads(run("read", lst.id, "--json").output)
    assert data["items"][0] == {"text": "milk", "checked": True}
