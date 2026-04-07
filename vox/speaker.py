"""Speaker label confirmation and replacement."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from . import ui


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

    ui.speakers_intro(len(speakers))

    mapping: dict[str, str] = {}

    for i, label in enumerate(speakers):
        preview = get_preview(transcript, label)
        clean_preview = re.sub(r"\[(?:en|zh|[a-z]{2})\]\s*", "", preview)
        snippet = clean_preview[:150] + "…" if len(clean_preview) > 150 else clean_preview
        ui.speaker_block(label, f'"{snippet}"')

        # Suggest from expected names if available
        suggestion = expected_names[i] if i < len(expected_names) else ""
        prompt = f"  Name [{suggestion}]: " if suggestion else "  Name: "
        raw = input(prompt).strip()
        if raw.lower() in ("q", "quit"):
            ui.muted("Stopped speaker mapping; remaining blocks keep Soniox labels.")
            break
        name = raw or suggestion
        if name:
            mapping[label] = name

    # Apply replacements
    result = transcript
    for label, name in mapping.items():
        result = result.replace(f"{label}:", f"{name}:")

    ui.get_console().print()
    return result


def replace_speakers_auto(transcript: str, names: list[str]) -> str:
    """Non-interactive speaker replacement (for scripted use)."""
    speakers = extract_speakers(transcript)
    result = transcript
    for i, label in enumerate(speakers):
        if i < len(names):
            result = result.replace(f"{label}:", f"{names[i]}:")
    return result


def auto_label_speakers(
    transcript: str,
    matches: dict[str, "VoiceprintMatch | None"],
) -> tuple[str, dict[str, str]]:
    """Apply high-confidence voiceprint matches to the transcript.

    Returns ``(updated_transcript, mapping)`` where ``mapping`` is
    ``{diar_label: human_name}`` for all confident matches.
    """
    from .voiceprint import VoiceprintMatch  # noqa: F811

    mapping: dict[str, str] = {}
    result = transcript

    for label, match in matches.items():
        if match is not None and match.confident:
            mapping[label] = match.name

    # Check for duplicate names (two speakers matched to the same person)
    name_counts: dict[str, list[str]] = {}
    for label, name in mapping.items():
        name_counts.setdefault(name, []).append(label)
    for name, labels in name_counts.items():
        if len(labels) > 1:
            # Ambiguous — keep the highest scoring one, remove others
            best_label = max(labels, key=lambda l: matches[l].score if matches[l] else 0)
            for label in labels:
                if label != best_label:
                    del mapping[label]

    for label, name in mapping.items():
        result = result.replace(f"{label}:", f"{name}:")

    return result, mapping


def confirm_speakers_with_voiceprint(
    transcript: str,
    matches: dict[str, "VoiceprintMatch | None"],
    expected_names: list[str],
) -> tuple[str, dict[str, str]]:
    """Interactive speaker confirmation with voiceprint-based suggestions.

    For confident matches, auto-fills the name. For low-confidence or unknown,
    falls back to manual confirmation with the voiceprint guess shown.

    Returns ``(updated_transcript, final_mapping)``.
    """
    from .voiceprint import VoiceprintMatch  # noqa: F811

    # First extract speaker labels from pyannote format (SPEAKER_00:)
    speakers = _extract_diar_speakers(transcript)
    if not speakers:
        # Fallback to Soniox format
        speakers = extract_speakers(transcript)
    if not speakers:
        return transcript, {}

    ui.speakers_intro(len(speakers))

    mapping: dict[str, str] = {}

    for i, label in enumerate(speakers):
        preview = get_preview(transcript, label)
        clean_preview = re.sub(r"\[(?:en|zh|[a-z]{2})\]\s*", "", preview)
        snippet = clean_preview[:150] + "…" if len(clean_preview) > 150 else clean_preview
        ui.speaker_block(label, f'"{snippet}"')

        # Build suggestion: voiceprint match > expected_names > nothing
        match = matches.get(label)
        if match is not None and match.confident:
            suggestion = match.name
            conf_hint = f" [voiceprint: {match.score:.2f}]"
        elif match is not None:
            suggestion = match.name
            conf_hint = f" [guess: {match.score:.2f}]"
        elif i < len(expected_names):
            suggestion = expected_names[i]
            conf_hint = ""
        else:
            suggestion = ""
            conf_hint = ""

        prompt = f"  Name [{suggestion}]{conf_hint}: " if suggestion else "  Name: "
        raw = input(prompt).strip()
        if raw.lower() in ("q", "quit"):
            ui.muted("Stopped speaker mapping; remaining blocks keep labels.")
            break
        name = raw or suggestion
        if name:
            mapping[label] = name

    result = transcript
    for label, name in mapping.items():
        result = result.replace(f"{label}:", f"{name}:")

    ui.get_console().print()
    return result, mapping


def _extract_diar_speakers(transcript: str) -> list[str]:
    """Extract unique SPEAKER_NN labels in order of appearance."""
    seen: set[str] = set()
    speakers: list[str] = []
    for m in re.finditer(r"^(SPEAKER_\d+):", transcript, re.MULTILINE):
        label = m.group(1)
        if label not in seen:
            seen.add(label)
            speakers.append(label)
    return speakers


# ---------------------------------------------------------------------------
# Non-interactive API (for server / GUI use)
# ---------------------------------------------------------------------------


@dataclass
class SpeakerPreview:
    """Preview data for a single speaker, used by the flashcard UI."""

    label: str  # e.g. "SPEAKER_00"
    text_snippet: str  # first few sentences
    best_segment_start_sec: float  # start of longest segment (for audio clip)
    best_segment_end_sec: float  # end of longest segment


def get_speaker_previews(
    transcript: str,
    segments: "list[Any]",
) -> list[SpeakerPreview]:
    """Build preview data for each speaker in the transcript.

    ``segments`` should be a list of ``DiarSegment`` objects.
    Returns a list of ``SpeakerPreview`` in order of appearance.
    """
    speakers = _extract_diar_speakers(transcript)
    if not speakers:
        speakers = extract_speakers(transcript)
    if not speakers:
        return []

    # Group segments by speaker, find the longest one per speaker
    from collections import defaultdict

    seg_by_speaker: dict[str, list[Any]] = defaultdict(list)
    for seg in segments:
        seg_by_speaker[seg.speaker].append(seg)

    previews: list[SpeakerPreview] = []
    for label in speakers:
        # Text preview
        preview_text = get_preview(transcript, label, max_sentences=3)
        clean = re.sub(r"\[(?:en|zh|[a-z]{2})\]\s*", "", preview_text)
        snippet = clean[:200]

        # Best audio clip: longest segment (2-8 seconds ideal)
        segs = seg_by_speaker.get(label, [])
        if segs:
            # Prefer segments between 2-8 seconds, fall back to longest
            good_segs = [s for s in segs if 2.0 <= (s.end_sec - s.start_sec) <= 8.0]
            if good_segs:
                best = max(good_segs, key=lambda s: s.end_sec - s.start_sec)
            else:
                best = max(segs, key=lambda s: s.end_sec - s.start_sec)
            start = best.start_sec
            end = min(best.end_sec, best.start_sec + 8.0)  # cap at 8s
        else:
            start = 0.0
            end = 5.0

        previews.append(SpeakerPreview(
            label=label,
            text_snippet=snippet,
            best_segment_start_sec=start,
            best_segment_end_sec=end,
        ))

    return previews


def apply_speaker_mapping(transcript: str, mapping: dict[str, str]) -> str:
    """Non-interactive speaker label replacement.

    ``mapping`` is ``{speaker_label: human_name}``, e.g.
    ``{"SPEAKER_00": "Jetson", "SPEAKER_01": "Kay"}``.
    """
    result = transcript
    for label, name in mapping.items():
        result = result.replace(f"{label}:", f"{name}:")
    return result
