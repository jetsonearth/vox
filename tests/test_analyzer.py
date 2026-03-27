"""Tests for analysis heading normalization."""

from vox.analyzer import _demote_analysis_headings


def test_demote_top_level_headings():
    raw = "# One\n\n## Two\n\nBody"
    assert _demote_analysis_headings(raw) == "## One\n\n### Two\n\nBody"


def test_demote_respects_six_hash_cap():
    raw = "##### Five\n###### Six"
    assert _demote_analysis_headings(raw) == "###### Five\n###### Six"


def test_non_headings_unchanged():
    raw = "not a # heading\n# real\n`# code`"
    assert _demote_analysis_headings(raw) == "not a # heading\n## real\n`# code`"
