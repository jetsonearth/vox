"""Tests for vox.align."""

from vox.align import AlignedToken, align_tokens_to_segments, render_aligned_tokens
from vox.diarize import DiarSegment
from vox.transcriber import Token


def _seg(start: float, end: float, speaker: str) -> DiarSegment:
    return DiarSegment(start_sec=start, end_sec=end, speaker=speaker)


def _tok(text: str, start_ms: int, end_ms: int, language: str = "en") -> Token:
    return Token(text=text, start_ms=start_ms, end_ms=end_ms, language=language)


def test_basic_alignment():
    segments = [
        _seg(0.0, 5.0, "SPEAKER_00"),
        _seg(5.0, 10.0, "SPEAKER_01"),
    ]
    tokens = [
        _tok("Hello ", 0, 2000),
        _tok("world. ", 2000, 4500),
        _tok("你好 ", 5500, 7000, "zh"),
        _tok("再见", 7500, 9000, "zh"),
    ]

    aligned = align_tokens_to_segments(tokens, segments)
    assert len(aligned) == 4
    assert aligned[0].speaker == "SPEAKER_00"
    assert aligned[1].speaker == "SPEAKER_00"
    assert aligned[2].speaker == "SPEAKER_01"
    assert aligned[3].speaker == "SPEAKER_01"


def test_overlap_picks_best_segment():
    """Token spanning two segments should go to the one with more overlap."""
    segments = [
        _seg(0.0, 3.0, "SPEAKER_00"),
        _seg(3.0, 10.0, "SPEAKER_01"),
    ]
    # Token from 2000-5000ms: 1000ms overlap with seg0, 2000ms overlap with seg1
    tokens = [_tok("overlap", 2000, 5000)]

    aligned = align_tokens_to_segments(tokens, segments)
    assert aligned[0].speaker == "SPEAKER_01"


def test_no_timestamp_carries_forward():
    """Tokens without timestamps should inherit the last speaker."""
    segments = [
        _seg(0.0, 5.0, "SPEAKER_00"),
        _seg(5.0, 10.0, "SPEAKER_01"),
    ]
    tokens = [
        _tok("Hello ", 1000, 2000),
        Token(text=" ", start_ms=0, end_ms=0, language=None),
        _tok("Bye", 6000, 7000),
    ]

    aligned = align_tokens_to_segments(tokens, segments)
    assert aligned[0].speaker == "SPEAKER_00"
    assert aligned[1].speaker == "SPEAKER_00"  # carries forward
    assert aligned[2].speaker == "SPEAKER_01"


def test_empty_segments_fallback():
    tokens = [_tok("Hello", 0, 1000)]
    aligned = align_tokens_to_segments(tokens, [])
    assert len(aligned) == 1
    assert aligned[0].speaker == "SPEAKER_00"


def test_nearest_segment_when_no_overlap():
    """Token outside all segments should snap to nearest."""
    segments = [
        _seg(0.0, 2.0, "SPEAKER_00"),
        _seg(8.0, 10.0, "SPEAKER_01"),
    ]
    # Token at 7000-7500ms: no overlap, but closer to SPEAKER_01
    tokens = [_tok("gap", 7000, 7500)]

    aligned = align_tokens_to_segments(tokens, segments)
    assert aligned[0].speaker == "SPEAKER_01"


def test_render_aligned_tokens():
    tokens = [
        AlignedToken(text="Hello ", start_ms=0, end_ms=1000, speaker="SPEAKER_00", language="en"),
        AlignedToken(text="world.", start_ms=1000, end_ms=2000, speaker="SPEAKER_00", language="en"),
        AlignedToken(text="你好", start_ms=3000, end_ms=4000, speaker="SPEAKER_01", language="zh"),
    ]

    text = render_aligned_tokens(tokens)
    assert "SPEAKER_00:" in text
    assert "SPEAKER_01:" in text
    assert "[en]" in text
    assert "[zh]" in text
    assert "Hello " in text
    assert "你好" in text


def test_render_language_switch():
    """Language switch within same speaker should insert language tag."""
    tokens = [
        AlignedToken(text="Hello ", start_ms=0, end_ms=500, speaker="SPEAKER_00", language="en"),
        AlignedToken(text="你好", start_ms=500, end_ms=1000, speaker="SPEAKER_00", language="zh"),
    ]

    text = render_aligned_tokens(tokens)
    assert "[en]" in text
    assert "[zh]" in text
    # Both under same SPEAKER_00
    assert text.count("SPEAKER_00:") == 1
