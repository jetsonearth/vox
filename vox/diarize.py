"""Speaker diarization via pyannote-audio."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import ui

_PIPELINE_CACHE: Any = None


@dataclass
class DiarSegment:
    """A single diarization segment."""

    start_sec: float
    end_sec: float
    speaker: str  # e.g. "SPEAKER_00"


def _get_device(cfg: dict[str, Any]) -> str:
    """Auto-detect best available device (MPS > CPU)."""
    device = cfg.get("diarization_device", "auto")
    if device != "auto":
        return device
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _load_pipeline(cfg: dict[str, Any]) -> Any:
    """Load and cache the pyannote speaker-diarization pipeline."""
    global _PIPELINE_CACHE
    if _PIPELINE_CACHE is not None:
        return _PIPELINE_CACHE

    try:
        from pyannote.audio import Pipeline
    except ImportError:
        raise RuntimeError(
            "pyannote-audio is not installed. "
            "Install with: pip install 'vox[diarize]'"
        )

    hf_token = cfg.get("hf_token") or None
    device = _get_device(cfg)

    with ui.timed_spinner("Loading pyannote diarization model…") as elapsed:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
        )
        import torch

        pipeline.to(torch.device(device))
    ui.ok(f"Diarization model loaded ({device})", elapsed())

    _PIPELINE_CACHE = pipeline
    return pipeline


def diarize(
    audio_path: str | Path,
    cfg: dict[str, Any],
    *,
    num_speakers: int | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> list[DiarSegment]:
    """Run speaker diarization on an audio file.

    Returns a list of ``DiarSegment`` sorted by start time.
    """
    pipeline = _load_pipeline(cfg)
    audio_path = str(audio_path)

    kwargs: dict[str, Any] = {}
    if num_speakers is not None:
        kwargs["num_speakers"] = num_speakers
    if min_speakers is not None:
        kwargs["min_speakers"] = min_speakers
    if max_speakers is not None:
        kwargs["max_speakers"] = max_speakers

    with ui.timed_spinner("Running speaker diarization…") as elapsed:
        diarization = pipeline(audio_path, **kwargs)
    ui.ok("Diarization complete", elapsed())

    segments: list[DiarSegment] = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append(
            DiarSegment(
                start_sec=turn.start,
                end_sec=turn.end,
                speaker=speaker,
            )
        )

    unique_speakers = {s.speaker for s in segments}
    ui.label_value("Speakers detected", str(len(unique_speakers)))
    return segments
