"""Text and JSON rendering of notes and labels."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime

from gkeepapi import node as gnode

from .resolve import color_name

SHORT_ID_LEN = 12


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _fmt_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def note_to_dict(note: gnode.TopLevelNode) -> dict:
    data = {
        "id": note.id,
        "server_id": note.server_id,
        "type": "list" if isinstance(note, gnode.List) else "note",
        "title": note.title,
        "color": color_name(note.color),
        "pinned": note.pinned,
        "archived": note.archived,
        "trashed": note.trashed,
        "labels": sorted(label.name for label in note.labels.all()),
        "created": _iso(note.timestamps.created),
        "updated": _iso(note.timestamps.updated),
        "edited": _iso(note.timestamps.edited),
    }
    if isinstance(note, gnode.List):
        data["items"] = [{"text": item.text, "checked": item.checked} for item in note.items]
        data["text"] = note.text
    else:
        data["text"] = note.text
    return data


def label_to_dict(label: gnode.Label) -> dict:
    return {"id": label.id, "name": label.name}


def to_json(payload) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def flags(note: gnode.TopLevelNode) -> str:
    out = ""
    out += "P" if note.pinned else "-"
    out += "A" if note.archived else "-"
    out += "T" if note.trashed else "-"
    out += "L" if isinstance(note, gnode.List) else "-"
    return out


def summary_line(note: gnode.TopLevelNode) -> str:
    title = note.title.strip() if note.title else ""
    if not title:
        body = note.text.strip() if note.text else ""
        title = body.splitlines()[0] if body else "(untitled)"
    return title


def render_table(notes: Iterable[gnode.TopLevelNode]) -> str:
    rows = []
    for note in notes:
        labels = ",".join(sorted(label.name for label in note.labels.all()))
        rows.append(
            (
                note.id[:SHORT_ID_LEN],
                flags(note),
                summary_line(note)[:60],
                labels,
                _fmt_time(note.timestamps.updated),
            )
        )
    if not rows:
        return "No notes found."
    header = ("ID", "FLAGS", "TITLE", "LABELS", "UPDATED")
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(header))]
    for row in rows:
        lines.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip())
    return "\n".join(lines)


def render_note(note: gnode.TopLevelNode) -> str:
    lines = [
        f"ID:       {note.id}",
        f"Title:    {note.title or '(untitled)'}",
        f"Type:     {'checklist' if isinstance(note, gnode.List) else 'note'}",
        f"Color:    {color_name(note.color)}",
        f"Labels:   {', '.join(sorted(label.name for label in note.labels.all())) or '-'}",
        f"Pinned:   {'yes' if note.pinned else 'no'}",
        f"Archived: {'yes' if note.archived else 'no'}",
    ]
    if note.trashed:
        lines.append("Trashed:  yes")
    lines.append(f"Created:  {_fmt_time(note.timestamps.created)}")
    lines.append(f"Updated:  {_fmt_time(note.timestamps.updated)}")
    lines.append("")
    if isinstance(note, gnode.List):
        for item in note.items:
            lines.append(f"[{'x' if item.checked else ' '}] {item.text}")
    else:
        lines.append(note.text or "")
    return "\n".join(lines).rstrip("\n")


def render_labels(labels: Iterable[gnode.Label]) -> str:
    names = sorted(label.name for label in labels)
    return "\n".join(names) if names else "No labels."
