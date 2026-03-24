"""Tests for vox.contacts."""

import tempfile
from pathlib import Path

from vox.contacts import fuzzy_match, scan_contacts


def test_scan_contacts_recursive():
    with tempfile.TemporaryDirectory() as tmpdir:
        rel_dir = Path(tmpdir)
        (rel_dir / "Terry Chen.md").write_text("# Terry", encoding="utf-8")
        (rel_dir / "Robotics").mkdir()
        (rel_dir / "Robotics" / "Tuo Liu.md").write_text("# Tuo", encoding="utf-8")

        contacts = scan_contacts(rel_dir)
        assert "Terry Chen" in contacts
        assert "Tuo Liu" in contacts
        assert len(contacts) == 2


def test_fuzzy_match():
    contacts = {
        "Terry Chen": Path("a.md"),
        "Tuo Liu": Path("b.md"),
        "Huey Lin": Path("c.md"),
    }
    assert fuzzy_match("terry", contacts) == "Terry Chen"
    assert fuzzy_match("tuo", contacts) == "Tuo Liu"
    assert fuzzy_match("xyzabc", contacts) is None


def test_scan_nonexistent_dir():
    assert scan_contacts(Path("/nonexistent/dir")) == {}
