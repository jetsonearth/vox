"""Tests for vox.cli date inference."""

import tempfile
from datetime import date
from pathlib import Path

from vox.cli import _infer_date


def test_infer_date_explicit_iso():
    assert _infer_date(Path("anything.m4a"), "2026-03-21") == date(2026, 3, 21)


def test_infer_date_explicit_mdyy():
    assert _infer_date(Path("anything.m4a"), "3-21-26") == date(2026, 3, 21)


def test_infer_date_from_filename_iso():
    assert _infer_date(Path("2026-03-21-terry.m4a"), None) == date(2026, 3, 21)


def test_infer_date_from_filename_mdyy():
    assert _infer_date(Path("terry-3-21-26.m4a"), None) == date(2026, 3, 21)


def test_infer_date_fallback_ctime():
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
        tmp = Path(f.name)
    try:
        result = _infer_date(tmp, None)
        assert result == date.today()
    finally:
        tmp.unlink(missing_ok=True)
