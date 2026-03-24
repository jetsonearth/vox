"""Slug generation, date formatting, and filename builders."""

from __future__ import annotations

import re
import unicodedata
from datetime import date


def make_slug(text: str) -> str:
    """Turn arbitrary text into a lowercase-hyphenated slug.

    >>> make_slug("RoboX Sync")
    'robox-sync'
    >>> make_slug("产品想法")
    '产品想法'
    """
    # Normalise unicode, strip accents on latin chars
    text = unicodedata.normalize("NFKC", text).strip()
    # Replace whitespace / underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Remove anything that isn't alphanumeric, hyphen, or CJK
    text = re.sub(r"[^\w\u4e00-\u9fff\u3400-\u4dbf-]", "", text)
    # Collapse multiple hyphens
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text.lower()


def make_daily_note_filename(d: date) -> str:
    """Return the daily note filename (ISO date, sorts chronologically in the file tree).

    >>> make_daily_note_filename(date(2026, 3, 23))
    '2026-03-23.md'
    """
    return f"{d.isoformat()}.md"


def make_audio_filename(d: date, slug: str) -> str:
    """Build the archived audio filename.

    >>> make_audio_filename(date(2026, 3, 23), "terry-gridmind")
    '2026-03-23-terry-gridmind.m4a'
    """
    return f"{d.isoformat()}-{slug}.m4a"


def make_transcript_filename(d: date, slug: str) -> str:
    """Build the transcript filename (Markdown in Obsidian Transcripts folder).

    >>> make_transcript_filename(date(2026, 3, 23), "terry-gridmind")
    '2026-03-23-terry-gridmind.md'
    """
    return f"{d.isoformat()}-{slug}.md"


def make_note_title(d: date, display_name: str) -> str:
    """Build the conversation note title (used as filename).

    >>> make_note_title(date(2026, 3, 23), "Terry Gridmind")
    '2026-03-23 Terry Gridmind'
    """
    return f"{d.isoformat()} {display_name}"


def make_archive_subdir(d: date) -> str:
    """Return the year/month subdirectory for audio archival.

    >>> make_archive_subdir(date(2026, 3, 23))
    '2026/03'
    """
    return f"{d.year}/{d.month:02d}"
