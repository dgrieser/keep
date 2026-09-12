"""Command-line interface for Google Keep."""

from __future__ import annotations

import functools
import logging
import re
import sys
from collections.abc import Callable

import click
from gkeepapi import node as gnode

from . import __version__, auth, client, render, resolve
from . import config as cfgmod
from .client import KeepError

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"], "max_content_width": 100}

_ITEM_LINE = re.compile(r"^\[(?P<mark>[ xX])\]\s?(?P<text>.*)$")


def handle_errors(fn: Callable) -> Callable:
    """Turn :class:`KeepError` into a clean message and exit code."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except KeepError as exc:
            click.echo(f"error: {exc}", err=True)
            sys.exit(exc.exit_code)
        except auth.AuthError as exc:
            click.echo(f"error: {exc}", err=True)
            sys.exit(1)

    return wrapper


def color_option(help_text: str):
    return click.option(
        "--color",
        "color",
        type=click.Choice(resolve.COLOR_CHOICES, case_sensitive=False),
        default=None,
        help=help_text,
    )


json_option = click.option("--json", "as_json", is_flag=True, help="Output JSON.")


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, prog_name="keep")
@click.option("-v", "--verbose", count=True, help="Increase log verbosity (-v, -vv).")
def main(verbose: int) -> None:
    """Manage Google Keep notes from the command line.

    Run `keep login` once to authorize, then use `keep list`, `keep read`, `keep create`,
    `keep edit` and `keep delete`. Note IDs may be abbreviated to any unique prefix.
    """
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


# --------------------------------------------------------------------------- auth


@main.command()
@click.option("--email", "email", default=None, help="Google account email.")
@click.option(
    "--oauth-token",
    "oauth_token",
    default=None,
    help="oauth_token cookie from accounts.google.com/EmbeddedSetup (prompted if omitted).",
)
@click.option(
    "--master-token",
    "master_token",
    default=None,
    help="Use an existing master token instead of exchanging an oauth_token.",
)
@handle_errors
def login(email: str | None, oauth_token: str | None, master_token: str | None) -> None:
    """Authorize this machine and store the credentials locally."""
    if not email:
        email = click.prompt("Google account email")
    email = email.strip()

    device_id = auth.new_android_id()
    if not master_token:
        if not oauth_token:
            click.echo(auth.LOGIN_INSTRUCTIONS)
            oauth_token = click.prompt("oauth_token", hide_input=True)
        master_token = auth.exchange_oauth_token(email, oauth_token, device_id)

    cfg = cfgmod.Config(email=email, master_token=master_token.strip(), device_id=device_id)
    client.verify_credentials(cfg)
    path = cfgmod.save_config(cfg)
    cfgmod.delete_state()
    click.echo(f"Logged in as {email}. Credentials stored in {path}.")


@main.command()
@handle_errors
def logout() -> None:
    """Remove stored credentials and the local cache."""
    removed_cfg = cfgmod.delete_config()
    cfgmod.delete_state()
    click.echo("Logged out." if removed_cfg else "No stored credentials found.")


# --------------------------------------------------------------------------- read


@main.command("list")
@click.option("-s", "--search", "search", default=None, help="Filter by text in title or body.")
@click.option("-l", "--label", "labels", multiple=True, help="Filter by label (repeatable).")
@color_option("Filter by color.")
@click.option("--pinned/--unpinned", "pinned", default=None, help="Filter by pinned state.")
@click.option("-a", "--archived", "archived", is_flag=True, help="Show only archived notes.")
@click.option("--all", "show_all", is_flag=True, help="Include archived notes.")
@click.option("--trashed", "trashed", is_flag=True, help="Show only trashed notes.")
@click.option("-n", "--limit", type=int, default=None, help="Show at most N notes.")
@json_option
@handle_errors
def list_notes(
    search: str | None,
    labels: tuple[str, ...],
    color: str | None,
    pinned: bool | None,
    archived: bool,
    show_all: bool,
    trashed: bool,
    limit: int | None,
    as_json: bool,
) -> None:
    """List notes (archived and trashed notes are hidden by default)."""
    keep = client.open_keep()

    label_objs = [resolve.find_label(keep, name) for name in labels] or None
    colors = [resolve.parse_color(color)] if color else None
    if archived:
        archived_filter: bool | None = True
    elif show_all or trashed:
        archived_filter = None
    else:
        archived_filter = False

    query = None
    if search:
        query = re.compile(re.escape(search), re.IGNORECASE)

    notes = list(
        keep.find(
            query=query,
            labels=label_objs,
            colors=colors,
            pinned=pinned,
            archived=archived_filter,
            trashed=trashed,
        )
    )
    if not trashed:
        notes = [n for n in notes if not n.trashed]
    notes.sort(key=lambda n: (not n.pinned, -(n.timestamps.updated.timestamp())))
    if limit is not None:
        notes = notes[:limit]

    if as_json:
        click.echo(render.to_json([render.note_to_dict(n) for n in notes]))
    else:
        click.echo(render.render_table(notes))


@main.command()
@click.argument("note_id")
@json_option
@handle_errors
def read(note_id: str, as_json: bool) -> None:
    """Show a single note in full."""
    keep = client.open_keep()
    note = resolve.find_note(keep, note_id)
    if as_json:
        click.echo(render.to_json(render.note_to_dict(note)))
    else:
        click.echo(render.render_note(note))


# --------------------------------------------------------------------------- create


def _read_stdin() -> str:
    return sys.stdin.read()


@main.command()
@click.argument("title", required=False, default=None)
@click.option("-t", "--text", "text", default=None, help="Note body.")
@click.option("--stdin", "from_stdin", is_flag=True, help="Read the note body from stdin.")
@click.option("-i", "--item", "items", multiple=True, help="Checklist item (repeatable).")
@click.option(
    "--checked", "checked_items", multiple=True, help="Checked checklist item (repeatable)."
)
@click.option("-l", "--label", "labels", multiple=True, help="Attach label (created if missing).")
@color_option("Note color.")
@click.option("--pin", is_flag=True, help="Pin the note.")
@click.option("--archive", is_flag=True, help="Create the note archived.")
@handle_errors
def create(
    title: str | None,
    text: str | None,
    from_stdin: bool,
    items: tuple[str, ...],
    checked_items: tuple[str, ...],
    labels: tuple[str, ...],
    color: str | None,
    pin: bool,
    archive: bool,
) -> None:
    """Create a note. Use --item to create a checklist instead of a text note."""
    is_list = bool(items or checked_items)
    if is_list and (text or from_stdin):
        raise KeepError("--item/--checked cannot be combined with --text/--stdin.", exit_code=2)
    if text is not None and from_stdin:
        raise KeepError("--text and --stdin are mutually exclusive.", exit_code=2)
    if from_stdin:
        text = _read_stdin()
    if not is_list and not title and not text:
        raise KeepError("Nothing to create: give a title, --text, --stdin or --item.", exit_code=2)

    keep = client.open_keep()
    if is_list:
        entries = [(i, False) for i in items] + [(i, True) for i in checked_items]
        note: gnode.TopLevelNode = keep.createList(title or "", entries)
    else:
        note = keep.createNote(title or "", text or "")

    for name in labels:
        note.labels.add(resolve.find_label(keep, name, create=True))
    if color:
        note.color = resolve.parse_color(color)
    if pin:
        note.pinned = True
    if archive:
        note.archived = True

    client.commit(keep)
    click.echo(note.id)


# --------------------------------------------------------------------------- edit


def _note_to_buffer(note: gnode.TopLevelNode) -> str:
    header = (
        "# First line is the title. Everything after the blank line is the body.\n"
        if not isinstance(note, gnode.List)
        else "# First line is the title. Then one item per line as '[ ] text' or '[x] text'.\n"
    )
    lines = [header, note.title or "", ""]
    if isinstance(note, gnode.List):
        lines += [f"[{'x' if i.checked else ' '}] {i.text}" for i in note.items]
    else:
        lines.append(note.text or "")
    return "\n".join(lines) + "\n"


def _parse_buffer(buffer: str) -> tuple[str, list[str]]:
    lines = buffer.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    if not lines:
        return "", []
    title = lines[0].strip()
    rest = lines[1:]
    if rest and rest[0].strip() == "":
        rest = rest[1:]
    return title, rest


def _apply_list_lines(note: gnode.List, lines: list[str]) -> None:
    wanted: list[tuple[str, bool]] = []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue
        m = _ITEM_LINE.match(line)
        if m:
            wanted.append((m.group("text").strip(), m.group("mark").lower() == "x"))
        else:
            wanted.append((line.strip(), False))

    remaining = list(note.items)
    ordered: list[gnode.ListItem] = []
    for text, checked in wanted:
        match = next((i for i in remaining if i.text == text), None)
        if match is None:
            match = note.add(text, checked, gnode.NewListItemPlacementValue.Bottom)
        else:
            remaining.remove(match)
            if match.checked != checked:
                match.checked = checked
        ordered.append(match)
    for leftover in remaining:
        leftover.delete()

    # Higher sort values are displayed first.
    base = 1_000_000 * max(len(ordered), 1)
    for idx, item in enumerate(ordered):
        item.sort = base - idx * 1_000


def _edit_in_editor(note: gnode.TopLevelNode) -> bool:
    edited = click.edit(_note_to_buffer(note), extension=".md")
    if edited is None:
        return False
    title, body_lines = _parse_buffer(edited)
    if title != (note.title or ""):
        note.title = title
    if isinstance(note, gnode.List):
        _apply_list_lines(note, body_lines)
    else:
        new_text = "\n".join(body_lines).rstrip("\n")
        if new_text != (note.text or ""):
            note.text = new_text
    return True


@main.command()
@click.argument("note_id")
@click.option("--title", "title", default=None, help="New title.")
@click.option("-t", "--text", "text", default=None, help="Replace the body.")
@click.option("--append", "append_text", default=None, help="Append a line to the body.")
@click.option("--stdin", "from_stdin", is_flag=True, help="Replace the body with stdin.")
@click.option("--add-item", "add_items", multiple=True, help="Add checklist item (repeatable).")
@click.option("--check", "check_items", multiple=True, help="Check item by index or text.")
@click.option("--uncheck", "uncheck_items", multiple=True, help="Uncheck item by index or text.")
@click.option("--remove-item", "remove_items", multiple=True, help="Remove item by index or text.")
@click.option("--pin/--unpin", "pinned", default=None, help="Pin or unpin.")
@click.option("--archive/--unarchive", "archived", default=None, help="Archive or unarchive.")
@color_option("Set the color.")
@click.option("--add-label", "add_labels", multiple=True, help="Add label (created if missing).")
@click.option("--remove-label", "remove_labels", multiple=True, help="Remove label.")
@click.option("-e", "--editor", "use_editor", is_flag=True, help="Edit title and body in $EDITOR.")
@handle_errors
def edit(
    note_id: str,
    title: str | None,
    text: str | None,
    append_text: str | None,
    from_stdin: bool,
    add_items: tuple[str, ...],
    check_items: tuple[str, ...],
    uncheck_items: tuple[str, ...],
    remove_items: tuple[str, ...],
    pinned: bool | None,
    archived: bool | None,
    color: str | None,
    add_labels: tuple[str, ...],
    remove_labels: tuple[str, ...],
    use_editor: bool,
) -> None:
    """Modify a note. With no options the note opens in $EDITOR."""
    body_opts = sum(1 for o in (text, append_text) if o is not None) + int(from_stdin)
    if body_opts > 1:
        raise KeepError("--text, --append and --stdin are mutually exclusive.", exit_code=2)

    has_flags = any(
        [
            title is not None,
            text is not None,
            append_text is not None,
            from_stdin,
            add_items,
            check_items,
            uncheck_items,
            remove_items,
            pinned is not None,
            archived is not None,
            color,
            add_labels,
            remove_labels,
        ]
    )
    if from_stdin:
        text = _read_stdin()

    keep = client.open_keep()
    note = resolve.find_note(keep, note_id)

    if use_editor or not has_flags:
        if not _edit_in_editor(note):
            click.echo("Edit aborted; note unchanged.", err=True)
            return

    if title is not None:
        note.title = title

    if text is not None or append_text is not None:
        if isinstance(note, gnode.List):
            raise KeepError(
                f"Note {note.id} is a checklist; use --add-item/--check/--remove-item.",
                exit_code=2,
            )
        if text is not None:
            note.text = text.rstrip("\n")
        if append_text is not None:
            current = note.text or ""
            note.text = f"{current}\n{append_text}" if current else append_text

    if add_items or check_items or uncheck_items or remove_items:
        lst = resolve.require_list(note)
        for sel in check_items:
            resolve.find_list_item(lst, sel).checked = True
        for sel in uncheck_items:
            resolve.find_list_item(lst, sel).checked = False
        for sel in remove_items:
            resolve.find_list_item(lst, sel).delete()
        for item_text in add_items:
            lst.add(item_text, False, gnode.NewListItemPlacementValue.Bottom)

    if pinned is not None:
        note.pinned = pinned
    if archived is not None:
        note.archived = archived
    if color:
        note.color = resolve.parse_color(color)
    for name in add_labels:
        note.labels.add(resolve.find_label(keep, name, create=True))
    for name in remove_labels:
        label = resolve.find_label(keep, name)
        note.labels.remove(label)

    client.commit(keep)
    click.echo(f"Updated {note.id}")


# --------------------------------------------------------------------------- delete


@main.command()
@click.argument("note_ids", nargs=-1, required=True)
@click.option("--permanent", is_flag=True, help="Delete permanently instead of moving to trash.")
@click.option("-y", "--yes", is_flag=True, help="Do not ask for confirmation.")
@handle_errors
def delete(note_ids: tuple[str, ...], permanent: bool, yes: bool) -> None:
    """Move notes to the trash (or delete permanently with --permanent)."""
    keep = client.open_keep()
    notes = [resolve.find_note(keep, ref) for ref in note_ids]

    if not yes:
        action = "Permanently delete" if permanent else "Trash"
        for note in notes:
            click.echo(f"  {note.id}  {render.summary_line(note)}")
        if not click.confirm(f"{action} {len(notes)} note(s)?", default=False):
            click.echo("Aborted.", err=True)
            sys.exit(1)

    for note in notes:
        if permanent:
            note.delete()
        else:
            note.trash()
    client.commit(keep)
    verb = "Deleted" if permanent else "Trashed"
    for note in notes:
        click.echo(f"{verb} {note.id}")


@main.command()
@click.argument("note_ids", nargs=-1, required=True)
@handle_errors
def restore(note_ids: tuple[str, ...]) -> None:
    """Restore notes from the trash."""
    keep = client.open_keep()
    notes = [resolve.find_note(keep, ref) for ref in note_ids]
    for note in notes:
        if not note.trashed:
            raise KeepError(f"Note {note.id} is not in the trash.", exit_code=2)
        note.untrash()
    client.commit(keep)
    for note in notes:
        click.echo(f"Restored {note.id}")


# --------------------------------------------------------------------------- labels


@main.group()
def labels() -> None:
    """Manage labels."""


@labels.command("list")
@json_option
@handle_errors
def labels_list(as_json: bool) -> None:
    """List all labels."""
    keep = client.open_keep()
    all_labels = list(keep.labels())
    if as_json:
        click.echo(
            render.to_json(
                sorted((render.label_to_dict(lb) for lb in all_labels), key=lambda d: d["name"])
            )
        )
    else:
        click.echo(render.render_labels(all_labels))


@labels.command("create")
@click.argument("name")
@handle_errors
def labels_create(name: str) -> None:
    """Create a label."""
    keep = client.open_keep()
    if keep.findLabel(name) is not None:
        raise KeepError(f"Label '{name}' already exists.", exit_code=2)
    label = keep.createLabel(name)
    client.commit(keep)
    click.echo(f"Created label '{label.name}'")


@labels.command("delete")
@click.argument("name")
@click.option("-y", "--yes", is_flag=True, help="Do not ask for confirmation.")
@handle_errors
def labels_delete(name: str, yes: bool) -> None:
    """Delete a label (notes keep their content, only the label is removed)."""
    keep = client.open_keep()
    label = resolve.find_label(keep, name)
    if not yes and not click.confirm(f"Delete label '{label.name}'?", default=False):
        click.echo("Aborted.", err=True)
        sys.exit(1)
    keep.deleteLabel(label.id)
    client.commit(keep)
    click.echo(f"Deleted label '{label.name}'")


if __name__ == "__main__":  # pragma: no cover
    main()
