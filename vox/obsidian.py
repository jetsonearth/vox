"""Obsidian note creation and daily note management."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from . import config as c
from . import naming
from . import ui


def build_frontmatter(
    d: date,
    people: list[str],
    topic: str,
    projects: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """Build YAML frontmatter matching existing vault pattern."""
    lines = ["---"]
    lines.append(f"date: {d.isoformat()}")
    if people:
        wikilinks = ", ".join(f"[[{p}]]" for p in people)
        lines.append(f"people: {wikilinks}")
    if projects:
        proj_links = ", ".join(f"[[{p}]]" for p in projects)
        lines.append(f"projects: {proj_links}")
    tag_list = tags or []
    if not tag_list:
        tag_list = ["#conversation"]
    lines.append(f"tags: {' '.join(tag_list)}")
    lines.append("---")
    return "\n".join(lines)


def create_conversation_note(
    d: date,
    display_name: str,
    people: list[str],
    transcript_filename: str,
    analysis: str | None,
    cfg: dict[str, Any],
    topic: str = "",
    projects: list[str] | None = None,
    tags: list[str] | None = None,
) -> Path:
    """Create the conversation note in ~/My Vault/Conversations/."""
    note_title = naming.make_note_title(d, display_name)
    note_path = c.conversations_dir(cfg) / f"{note_title}.md"

    if note_path.exists():
        action = input(f"Note already exists: {note_path.name}\n  [o]verwrite / [a]ppend analysis / [s]kip: ").strip().lower()
        if action == "s":
            ui.muted(f"Skipped note: {note_path}")
            return note_path
        elif action == "a" and analysis:
            existing = note_path.read_text(encoding="utf-8")
            if "# Analysis" in existing:
                head = existing.split("# Analysis", 1)[0]
            elif "## Analysis" in existing:
                head = existing.split("## Analysis", 1)[0]
            else:
                head = existing
            head = head.rstrip()
            head = re.sub(r"\n---\s*$", "", head).rstrip()
            note_path.write_text(
                head + "\n\n---\n\n# Analysis\n\n" + analysis.lstrip("\n") + "\n",
                encoding="utf-8",
            )
            ui.ok(f"Analysis appended → {note_path}")
            return note_path
        # else: overwrite

    frontmatter = build_frontmatter(d, people, topic, projects, tags)
    body_parts = [
        frontmatter,
        "# Transcript",
        "",
        f"[[Transcripts/{transcript_filename}]]",
        "",
        "---",
        "",
        "# Analysis",
        "",
    ]
    if analysis:
        body_parts.append(analysis.lstrip("\n"))
    else:
        body_parts.append("*(Run analysis to populate this section)*")
    body_parts.append("")

    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("\n".join(body_parts), encoding="utf-8")
    ui.ok(f"Conversation note → {note_path}")
    return note_path


def save_transcript(
    d: date,
    slug: str,
    transcript_text: str,
    cfg: dict[str, Any],
    *,
    announce: bool = True,
) -> str:
    """Save transcript as ``.txt`` under Conversations/Transcripts/. Returns the filename."""
    filename = naming.make_transcript_txt_filename(d, slug)
    transcript_path = c.transcripts_dir(cfg) / filename
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(transcript_text, encoding="utf-8")
    if announce:
        ui.ok(f"Transcript saved → {transcript_path}")
    return filename


def ensure_daily_note(d: date, cfg: dict[str, Any]) -> Path:
    """Create daily note from template if none exists for that date. Returns path.

    Prefers exact ``YYYY-MM-DD.md``; if only suffixed dailies exist (e.g.
    ``2026-03-09 (Terry Chat).md``), uses the first matching file instead of
    creating a duplicate bare ISO file.
    """
    cal = c.calendar_dir(cfg)
    prefix = d.isoformat()
    exact = cal / f"{prefix}.md"
    if exact.is_file():
        return exact
    matches = sorted(cal.glob(f"{prefix}*.md"))
    if matches:
        return matches[0]

    filename = naming.make_daily_note_filename(d)
    daily_path = cal / filename

    if not daily_path.exists():
        template_path = c.templates_dir(cfg) / "Daily Note Template.md"
        if template_path.exists():
            content = template_path.read_text(encoding="utf-8")
        else:
            content = f"# {d.isoformat()}\n\n## Log\n\n## Conversations\n\n## Tomorrow\n"
        daily_path.parent.mkdir(parents=True, exist_ok=True)
        daily_path.write_text(content, encoding="utf-8")
        ui.ok(f"Created daily note → {daily_path}")

    return daily_path


def append_to_conversations_section(daily_path: Path, note_title: str) -> None:
    """Append a [[wikilink]] to the Conversations section of the daily note.

    Idempotent — skips if the link is already present.
    """
    content = daily_path.read_text(encoding="utf-8")
    wikilink = f"[[{note_title}]]"

    if wikilink in content:
        return  # Already linked

    # Find the ## Conversations section and append
    if "## Conversations" in content:
        content = content.replace(
            "## Conversations\n",
            f"## Conversations\n- {wikilink}\n",
        )
    else:
        # No Conversations section — append at end
        content = content.rstrip() + f"\n\n## Conversations\n- {wikilink}\n"

    daily_path.write_text(content, encoding="utf-8")
    ui.ok(f"Linked in daily note: {wikilink}")
