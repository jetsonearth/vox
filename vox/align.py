"""Align Soniox tokens to pyannote diarization segments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .diarize import DiarSegment
from .transcriber import Token


@dataclass
class AlignedToken:
    """A token with an assigned speaker from diarization."""

    text: str
    start_ms: int
    end_ms: int
    speaker: str  # e.g. "SPEAKER_00"
    language: str | None = None


def _overlap_ms(tok_start: int, tok_end: int, seg_start_ms: int, seg_end_ms: int) -> int:
    """Compute overlap in ms between a token and a segment."""
    start = max(tok_start, seg_start_ms)
    end = min(tok_end, seg_end_ms)
    return max(0, end - start)


def align_tokens_to_segments(
    tokens: list[Token],
    segments: list[DiarSegment],
) -> list[AlignedToken]:
    """Assign each token to the diarization segment with max overlap.

    Falls back to nearest segment by midpoint if no overlap found.
    """
    if not segments:
        return [
            AlignedToken(
                text=t.text,
                start_ms=t.start_ms,
                end_ms=t.end_ms,
                speaker="SPEAKER_00",
                language=t.language,
            )
            for t in tokens
        ]

    # Pre-convert segments to ms for faster comparison
    seg_ms = [(int(s.start_sec * 1000), int(s.end_sec * 1000), s.speaker) for s in segments]

    aligned: list[AlignedToken] = []
    last_speaker: str = segments[0].speaker

    for token in tokens:
        if token.start_ms == 0 and token.end_ms == 0:
            # No timestamp — carry forward last speaker
            aligned.append(
                AlignedToken(
                    text=token.text,
                    start_ms=0,
                    end_ms=0,
                    speaker=last_speaker,
                    language=token.language,
                )
            )
            continue

        best_speaker: Optional[str] = None
        best_overlap = 0

        for seg_start, seg_end, seg_spk in seg_ms:
            ovlp = _overlap_ms(token.start_ms, token.end_ms, seg_start, seg_end)
            if ovlp > best_overlap:
                best_overlap = ovlp
                best_speaker = seg_spk

        if best_speaker is None:
            # No overlap — find nearest segment by token midpoint
            mid = (token.start_ms + token.end_ms) / 2
            best_dist = float("inf")
            for seg_start, seg_end, seg_spk in seg_ms:
                seg_mid = (seg_start + seg_end) / 2
                dist = abs(mid - seg_mid)
                if dist < best_dist:
                    best_dist = dist
                    best_speaker = seg_spk

        speaker = best_speaker or last_speaker
        last_speaker = speaker

        aligned.append(
            AlignedToken(
                text=token.text,
                start_ms=token.start_ms,
                end_ms=token.end_ms,
                speaker=speaker,
                language=token.language,
            )
        )

    return aligned


def render_aligned_tokens(tokens: list[AlignedToken]) -> str:
    """Render aligned tokens into a readable transcript, grouped by speaker."""
    parts: list[str] = []
    current_speaker: Optional[str] = None
    current_language: Optional[str] = None

    for token in tokens:
        if token.speaker != current_speaker:
            if current_speaker is not None:
                parts.append("\n\n")
            current_speaker = token.speaker
            current_language = None
            parts.append(f"{current_speaker}:")

        if token.language is not None and token.language != current_language:
            current_language = token.language
            parts.append(f"\n[{current_language}] ")
            text = token.text.lstrip()
        else:
            text = token.text

        parts.append(text)

    return "".join(parts)
