"""Fuzzy match vault contacts in PRM/Relationships/."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from . import ui


def scan_contacts(relationships_dir: Path) -> dict[str, Path]:
    """Recursively scan PRM/Relationships/ for .md files.

    Returns {display_name: path} where display_name is the file stem.
    """
    contacts: dict[str, Path] = {}
    if not relationships_dir.exists():
        return contacts
    for md in relationships_dir.rglob("*.md"):
        contacts[md.stem] = md
    return contacts


def _canonical_user_name(raw: str, cfg: dict[str, Any]) -> str | None:
    """If ``raw`` matches ``user_name`` in config (case-insensitive), return canonical name."""
    me = (cfg.get("user_name") or "").strip()
    if not me:
        return None
    if raw.strip().lower() == me.lower():
        return me
    return None


def fuzzy_match(name: str, contacts: dict[str, Path], threshold: float = 0.4) -> str | None:
    """Find the closest matching contact name. Returns None if no good match."""
    if not contacts:
        return None
    matches = difflib.get_close_matches(name, contacts.keys(), n=1, cutoff=threshold)
    return matches[0] if matches else None


def resolve_people(raw_names: list[str], cfg: dict[str, Any]) -> list[str]:
    """Resolve a list of raw name inputs to vault contact names.

    For each name:
    1. Try exact match (case-insensitive) in PRM/Relationships
    2. Try match against ``user_name`` in config (you — no stub card)
    3. Try fuzzy match in PRM
    4. If no match, offer to create a stub card
    """
    from . import config as c

    relationships_dir = c.prm_relationships_dir(cfg)
    contacts = scan_contacts(relationships_dir)

    # Build lowercase lookup
    lower_map = {k.lower(): k for k in contacts}

    resolved: list[str] = []
    for raw in raw_names:
        raw = raw.strip()
        if not raw:
            continue

        # Exact match (case-insensitive)
        if raw.lower() in lower_map:
            resolved.append(lower_map[raw.lower()])
            continue

        # Config user_name = self (no PRM stub for your own name)
        self_name = _canonical_user_name(raw, cfg)
        if self_name is not None:
            resolved.append(self_name)
            continue

        # Fuzzy match
        match = fuzzy_match(raw, contacts)
        if match:
            confirm = input(f"  Did you mean \"{match}\"? [Y/n]: ").strip().lower()
            if confirm in ("", "y", "yes"):
                resolved.append(match)
                continue

        # No match — use as-is (title-cased)
        display = raw.title() if raw.isascii() else raw
        ui.info(f"New contact: {display}")
        create = input(f"  Create stub card for {display}? [Y/n]: ").strip().lower()
        if create in ("", "y", "yes"):
            _create_stub(relationships_dir, display)
        resolved.append(display)

    return resolved


def _create_stub(relationships_dir: Path, name: str) -> None:
    """Create a minimal PRM relationship card."""
    card_path = relationships_dir / f"{name}.md"
    if card_path.exists():
        return
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(
        f"---\nname: {name}\ntags: #contact\n---\n\n## Notes\n\n",
        encoding="utf-8",
    )
    ui.ok(f"Stub card → {card_path}")
