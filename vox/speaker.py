"""Speaker label confirmation and replacement."""

from __future__ import annotations

import re


def extract_speakers(transcript: str) -> list[str]:
    """Return unique speaker labels in order of appearance."""
    seen: set[str] = set()
    speakers: list[str] = []
    for m in re.finditer(r"^(Speaker \d+):", transcript, re.MULTILINE):
        label = m.group(1)
        if label not in seen:
            seen.add(label)
            speakers.append(label)
    return speakers


def get_preview(transcript: str, speaker_label: str, max_sentences: int = 2) -> str:
    """Extract the first N sentences for a given speaker label."""
    pattern = re.compile(
        rf"^{re.escape(speaker_label)}:\n(.*?)(?=\n\nSpeaker \d+:|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(transcript)
    if not m:
        return "(no text found)"
    text = m.group(1).strip()
    # Split on sentence-ending punctuation (including Chinese)
    sentences = re.split(r"(?<=[.!?。！？])\s*", text)
    preview = " ".join(s.strip() for s in sentences[:max_sentences] if s.strip())
    return preview or text[:200]


def confirm_speakers(transcript: str, expected_names: list[str]) -> str:
    """Interactive speaker confirmation. Returns transcript with names replaced.

    If expected_names are provided and match the speaker count,
    auto-maps them in order with user confirmation.
    """
    speakers = extract_speakers(transcript)
    if not speakers:
        return transcript

    print(f"\nFound {len(speakers)} speaker(s) in transcript:\n")

    mapping: dict[str, str] = {}

    for i, label in enumerate(speakers):
        preview = get_preview(transcript, label)
        print(f"  {label}:")
        # Strip language tags for preview display
        clean_preview = re.sub(r"\[(?:en|zh|[a-z]{2})\]\s*", "", preview)
        print(f"    \"{clean_preview[:150]}...\"" if len(clean_preview) > 150 else f"    \"{clean_preview}\"")

        # Suggest from expected names if available
        suggestion = expected_names[i] if i < len(expected_names) else ""
        if suggestion:
            name = input(f"  Name [{suggestion}]: ").strip() or suggestion
        else:
            name = input("  Name: ").strip()

        if name:
            mapping[label] = name

    # Apply replacements
    result = transcript
    for label, name in mapping.items():
        result = result.replace(f"{label}:", f"{name}:")

    print()
    return result


def replace_speakers_auto(transcript: str, names: list[str]) -> str:
    """Non-interactive speaker replacement (for scripted use)."""
    speakers = extract_speakers(transcript)
    result = transcript
    for i, label in enumerate(speakers):
        if i < len(names):
            result = result.replace(f"{label}:", f"{names[i]}:")
    return result
