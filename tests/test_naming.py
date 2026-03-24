"""Tests for vox.naming."""

from datetime import date

from vox.naming import (
    make_archive_subdir,
    make_audio_filename,
    make_daily_note_filename,
    make_note_title,
    make_slug,
    make_transcript_filename,
)


def test_make_slug():
    assert make_slug("RoboX Sync") == "robox-sync"
    assert make_slug("Terry Chen") == "terry-chen"
    assert make_slug("产品想法") == "产品想法"
    assert make_slug("  hello   world  ") == "hello-world"
    assert make_slug("德国🇩🇪Zillou") == "德国zillou"
    assert make_slug("Phanos H. @ 2050 Materials") == "phanos-h-2050-materials"


def test_make_daily_note_filename():
    assert make_daily_note_filename(date(2026, 3, 23)) == "2026-03-23.md"
    assert make_daily_note_filename(date(2025, 10, 5)) == "2025-10-05.md"


def test_make_audio_filename():
    assert make_audio_filename(date(2026, 3, 23), "terry-chen") == "2026-03-23-terry-chen.m4a"


def test_make_transcript_filename():
    assert make_transcript_filename(date(2026, 3, 23), "terry-chen") == "2026-03-23-terry-chen.md"


def test_make_note_title():
    assert make_note_title(date(2026, 3, 23), "Terry Chen") == "2026-03-23 Terry Chen"


def test_make_archive_subdir():
    assert make_archive_subdir(date(2026, 3, 23)) == "2026/03"
    assert make_archive_subdir(date(2025, 1, 5)) == "2025/01"
