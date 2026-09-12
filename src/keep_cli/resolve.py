"""Helpers for turning user input into gkeepapi objects."""

from __future__ import annotations

import gkeepapi
from gkeepapi import node as gnode

from .client import KeepError

COLOR_NAMES: dict[str, gnode.ColorValue] = {c.name.lower(): c for c in gnode.ColorValue}
COLOR_CHOICES = sorted(COLOR_NAMES)


def parse_color(value: str) -> gnode.ColorValue:
    key = value.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    if key == "default":
        key = "white"
    try:
        return COLOR_NAMES[key]
    except KeyError:
        raise KeepError(
            f"Unknown color '{value}'. Choose one of: {', '.join(COLOR_CHOICES)}", exit_code=2
        ) from None


def color_name(color: gnode.ColorValue) -> str:
    return color.name.lower()


def find_note(keep: gkeepapi.Keep, ref: str) -> gnode.TopLevelNode:
    """Find a note by exact id, exact server id, or unique id prefix."""
    ref = ref.strip()
    if not ref:
        raise KeepError("Empty note id.", exit_code=2)

    exact = keep.get(ref)
    if exact is not None:
        return exact

    candidates = list(keep.all())
    matches = [n for n in candidates if n.server_id == ref]
    if len(matches) == 1:
        return matches[0]

    matches = [
        n
        for n in candidates
        if n.id.startswith(ref) or (n.server_id and n.server_id.startswith(ref))
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeepError(f"No note found matching '{ref}'.", exit_code=2)

    listing = "\n".join(f"  {n.id}  {n.title or '(untitled)'}" for n in matches[:10])
    raise KeepError(f"Note id '{ref}' is ambiguous. Candidates:\n{listing}", exit_code=2)


def find_label(keep: gkeepapi.Keep, name: str, *, create: bool = False) -> gnode.Label:
    name = name.strip()
    if not name:
        raise KeepError("Empty label name.", exit_code=2)
    label = keep.findLabel(name, create=create)
    if label is None:
        raise KeepError(f"No label named '{name}'.", exit_code=2)
    return label


def find_list_item(note: gnode.List, selector: str) -> gnode.ListItem:
    """Select a checklist item by 1-based index or by exact (case-insensitive) text."""
    items = note.items
    sel = selector.strip()
    if sel.isdigit():
        idx = int(sel)
        if 1 <= idx <= len(items):
            return items[idx - 1]
        raise KeepError(
            f"Item index {idx} is out of range (list has {len(items)} items).", exit_code=2
        )
    matches = [i for i in items if i.text == sel]
    if not matches:
        matches = [i for i in items if i.text.lower() == sel.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeepError(f"No checklist item matching '{selector}'.", exit_code=2)
    raise KeepError(
        f"Checklist item '{selector}' is ambiguous; use its index (1-{len(items)}) instead.",
        exit_code=2,
    )


def require_list(note: gnode.TopLevelNode) -> gnode.List:
    if not isinstance(note, gnode.List):
        raise KeepError(
            f"Note {note.id} is not a checklist; item options only apply to checklists.",
            exit_code=2,
        )
    return note
