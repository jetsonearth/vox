"""Tests for vox.contacts."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from vox.contacts import fuzzy_match, resolve_people, scan_contacts


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


def test_resolve_user_name_matches_config_no_stub_prompt():
    """Passing your own name from config must not prompt for a PRM stub."""
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        (vault / "PRM" / "Relationships").mkdir(parents=True)
        cfg = {"vault_path": str(vault), "user_name": "Jetson"}
        with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            assert resolve_people(["Jetson"], cfg) == ["Jetson"]
            assert resolve_people(["jetson"], cfg) == ["Jetson"]


def test_resolve_user_name_after_prm_exact():
    """PRM exact match wins over config user_name (same string uses PRM stem)."""
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        rel = vault / "PRM" / "Relationships"
        rel.mkdir(parents=True)
        (rel / "Jetson.md").write_text("---\n---\n", encoding="utf-8")
        cfg = {"vault_path": str(vault), "user_name": "Someone Else"}
        with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            assert resolve_people(["Jetson"], cfg) == ["Jetson"]
