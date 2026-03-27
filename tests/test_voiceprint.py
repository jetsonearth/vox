"""Tests for vox.voiceprint (mocked models)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

np = pytest.importorskip("numpy", reason="numpy required for voiceprint tests")

from vox.diarize import DiarSegment
from vox.voiceprint import VoiceprintMatch, _load_all_voiceprints, enroll, match_speakers


@pytest.fixture
def vp_dir(tmp_path):
    """Provide a temp voiceprints directory and matching cfg."""
    vp = tmp_path / "voiceprints"
    vp.mkdir()
    cfg = {"voiceprint_threshold": 0.65, "auto_learn_voiceprints": True}
    with patch("vox.voiceprint._voiceprints_dir", return_value=vp):
        yield vp, cfg


def test_enroll_creates_file(vp_dir):
    vp, cfg = vp_dir
    import numpy as np

    emb = np.random.randn(192).astype(np.float32)
    emb /= np.linalg.norm(emb)

    with patch("vox.voiceprint._voiceprints_dir", return_value=vp):
        filepath = enroll("Jetson", emb, cfg, source="test")

    assert filepath.exists()
    assert filepath.name == "Jetson_000.npy"

    # Check index
    index = json.loads((vp / "index.json").read_text())
    assert "Jetson" in index
    assert len(index["Jetson"]) == 1
    assert index["Jetson"][0]["source"] == "test"


def test_enroll_increments_counter(vp_dir):
    vp, cfg = vp_dir
    import numpy as np

    emb = np.random.randn(192).astype(np.float32)
    with patch("vox.voiceprint._voiceprints_dir", return_value=vp):
        enroll("Jetson", emb, cfg)
        filepath2 = enroll("Jetson", emb, cfg)

    assert filepath2.name == "Jetson_001.npy"


def test_load_all_voiceprints(vp_dir):
    vp, cfg = vp_dir
    import numpy as np

    emb1 = np.random.randn(192).astype(np.float32)
    emb1 /= np.linalg.norm(emb1)
    emb2 = np.random.randn(192).astype(np.float32)
    emb2 /= np.linalg.norm(emb2)

    with patch("vox.voiceprint._voiceprints_dir", return_value=vp):
        enroll("Alice", emb1, cfg)
        enroll("Bob", emb2, cfg)
        loaded = _load_all_voiceprints(cfg)

    assert "Alice" in loaded
    assert "Bob" in loaded
    # Should be normalized
    for name, emb in loaded.items():
        assert abs(np.linalg.norm(emb) - 1.0) < 1e-5


def test_match_speakers_no_enrolled(vp_dir):
    vp, cfg = vp_dir
    segments = [
        DiarSegment(0.0, 5.0, "SPEAKER_00"),
        DiarSegment(5.0, 10.0, "SPEAKER_01"),
    ]

    with patch("vox.voiceprint._voiceprints_dir", return_value=vp):
        matches = match_speakers("fake.wav", segments, cfg)

    assert matches["SPEAKER_00"] is None
    assert matches["SPEAKER_01"] is None


def test_voiceprint_match_dataclass():
    m = VoiceprintMatch(name="Jetson", score=0.82, confident=True)
    assert m.confident
    assert m.score == 0.82

    m2 = VoiceprintMatch(name="Unknown", score=0.45, confident=False)
    assert not m2.confident
