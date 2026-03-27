"""Tests for vox.transcriber (no API)."""

from vox.transcriber import Token, TranscriptResult, render_tokens


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


def test_token_from_soniox():
    raw = {
        "text": "Hello",
        "start_ms": 100,
        "end_ms": 500,
        "speaker": 0,
        "language": "en",
    }
    tok = Token.from_soniox(raw)
    assert tok.text == "Hello"
    assert tok.start_ms == 100
    assert tok.end_ms == 500
    assert tok.speaker == 0
    assert tok.language == "en"


def test_token_from_soniox_missing_fields():
    raw = {"text": "Hi"}
    tok = Token.from_soniox(raw)
    assert tok.text == "Hi"
    assert tok.start_ms == 0
    assert tok.end_ms == 0
    assert tok.speaker is None
    assert tok.language is None


def test_transcript_result_str():
    tr = TranscriptResult(text="Hello world", tokens=[], raw_tokens=[])
    assert str(tr) == "Hello world"
    assert tr.text == "Hello world"
