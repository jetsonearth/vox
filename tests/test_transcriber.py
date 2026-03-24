"""Tests for vox.transcriber (no API)."""

from vox.transcriber import render_tokens


def test_render_tokens():
    tokens = [
        {"text": "Hello ", "speaker": 0, "language": "en"},
        {"text": "how are you?", "speaker": 0, "language": "en"},
        {"text": "我很好", "speaker": 1, "language": "zh"},
        {"text": " thank you.", "speaker": 1, "language": "en"},
    ]

    result = render_tokens(tokens)
    assert "Speaker 0:" in result
    assert "Speaker 1:" in result
    assert "[en]" in result
    assert "[zh]" in result
    assert "Hello " in result
    assert "我很好" in result
