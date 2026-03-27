"""Tests for vox.obsidian."""

import tempfile
from datetime import date
from pathlib import Path

from vox.obsidian import (
    append_to_conversations_section,
    build_frontmatter,
    ensure_daily_note,
    save_transcript,
)


def test_build_frontmatter():
    fm = build_frontmatter(date(2026, 3, 23), ["Terry Chen"], "Gridmind")
    assert "date: 2026-03-23" in fm
    assert "[[Terry Chen]]" in fm
    assert "---" in fm


def test_build_frontmatter_solo_no_people_line():
    fm_solo = build_frontmatter(date(2026, 3, 23), [], "Brain dump")
    assert "people:" not in fm_solo


def test_save_transcript():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = {"vault_path": tmpdir}
        (Path(tmpdir) / "Conversations" / "Transcripts").mkdir(parents=True)
        filename = save_transcript(date(2026, 3, 23), "terry-chen", "Hello world transcript", cfg)
        assert filename == "2026-03-23-terry-chen.txt"
        saved = (Path(tmpdir) / "Conversations" / "Transcripts" / filename).read_text()
        assert saved == "Hello world transcript"


def test_ensure_daily_note_from_template():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = {"vault_path": tmpdir}
        cal_dir = Path(tmpdir) / "Calendar"
        cal_dir.mkdir()
        tmpl_dir = Path(tmpdir) / "Templates"
        tmpl_dir.mkdir()
        (tmpl_dir / "Daily Note Template.md").write_text("## Log\n\n## Conversations\n")

        daily = ensure_daily_note(date(2026, 3, 23), cfg)
        assert daily.exists()
        assert daily.name == "2026-03-23.md"
        content = daily.read_text()
        assert "## Conversations" in content


def test_ensure_daily_note_finds_suffixed_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = {"vault_path": tmpdir}
        cal_dir = Path(tmpdir) / "Calendar"
        cal_dir.mkdir()
        suffixed = cal_dir / "2026-03-09 (Terry Chat).md"
        suffixed.write_text("existing note")

        daily = ensure_daily_note(date(2026, 3, 9), cfg)
        assert daily == suffixed


def test_append_to_conversations_section_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        daily = Path(tmpdir) / "test.md"
        daily.write_text("## Log\n\n## Conversations\n\n## Tomorrow\n")

        append_to_conversations_section(daily, "2026-03-23 Terry Chen")
        content = daily.read_text()
        assert "[[2026-03-23 Terry Chen]]" in content

        append_to_conversations_section(daily, "2026-03-23 Terry Chen")
        content2 = daily.read_text()
        assert content2.count("[[2026-03-23 Terry Chen]]") == 1
