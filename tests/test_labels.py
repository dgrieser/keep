import json


def test_labels_list(keep, run):
    result = run("labels", "list")
    assert result.output.splitlines() == ["todo", "work"]
    data = json.loads(run("labels", "list", "--json").output)
    assert [d["name"] for d in data] == ["todo", "work"]


def test_labels_create(keep, run):
    result = run("labels", "create", "ideas")
    assert result.exit_code == 0
    assert keep.findLabel("ideas") is not None
    assert keep.commits == 1
    dup = run("labels", "create", "ideas")
    assert dup.exit_code == 2


def test_labels_delete(keep, run):
    label = keep.findLabel("work")
    result = run("labels", "delete", "work", "-y")
    assert result.exit_code == 0
    assert keep.getLabel(label.id) is None or label.deleted
    missing = run("labels", "delete", "nothing", "-y")
    assert missing.exit_code == 2
