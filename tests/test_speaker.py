"""Tests for vox.speaker."""

from vox.speaker import extract_speakers, get_preview, replace_speakers_auto

TRANSCRIPT = """Speaker 0:
[en] Hello, how are you doing today?

Speaker 1:
[zh] 我很好，谢谢你。
[en] Let's talk about the project.

Speaker 0:
[en] Sure, I have some updates."""


def test_extract_speakers():
    speakers = extract_speakers(TRANSCRIPT)
    assert speakers == ["Speaker 0", "Speaker 1"]


def test_get_preview():
    preview = get_preview(TRANSCRIPT, "Speaker 0")
    assert "Hello" in preview

    preview1 = get_preview(TRANSCRIPT, "Speaker 1")
    assert len(preview1) > 0


def test_replace_speakers_auto():
    result = replace_speakers_auto(TRANSCRIPT, ["Jetson", "Terry Chen"])
    assert "Jetson:" in result
    assert "Terry Chen:" in result
    assert "Speaker 0:" not in result
    assert "Speaker 1:" not in result


def test_empty_transcript():
    assert extract_speakers("No speakers here") == []
    assert replace_speakers_auto("No speakers here", ["Name"]) == "No speakers here"
