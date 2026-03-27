"""Voiceprint enrollment and matching using SpeechBrain ECAPA-TDNN."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from . import ui
from .diarize import DiarSegment

_ENCODER_CACHE: Any = None


@dataclass
class VoiceprintMatch:
    """Result of matching a speaker against the voiceprint database."""

    name: str
    score: float  # cosine similarity
    confident: bool  # score >= threshold


def _get_encoder(cfg: dict[str, Any]) -> Any:
    """Load and cache the SpeechBrain ECAPA-TDNN encoder."""
    global _ENCODER_CACHE
    if _ENCODER_CACHE is not None:
        return _ENCODER_CACHE

    try:
        from speechbrain.inference.speaker import EncoderClassifier
    except ImportError:
        raise RuntimeError(
            "speechbrain is not installed. "
            "Install with: pip install 'vox[diarize]'"
        )

    device = cfg.get("diarization_device", "auto")
    if device == "auto":
        try:
            import torch

            device = "mps" if torch.backends.mps.is_available() else "cpu"
        except Exception:
            device = "cpu"

    with ui.timed_spinner("Loading SpeechBrain ECAPA-TDNN model…") as elapsed:
        encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": device},
        )
    ui.ok(f"Speaker embedding model loaded ({device})", elapsed())

    _ENCODER_CACHE = encoder
    return encoder


def _voiceprints_dir(cfg: dict[str, Any]) -> Path:
    """Return the voiceprints storage directory."""
    from . import config as c

    return c.voiceprints_dir(cfg)


def _index_path(cfg: dict[str, Any]) -> Path:
    return _voiceprints_dir(cfg) / "index.json"


def _load_index(cfg: dict[str, Any]) -> dict:
    """Load the voiceprint index. Structure: {name: [{file, source, enrolled_at}]}."""
    path = _index_path(cfg)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_index(cfg: dict[str, Any], index: dict) -> None:
    path = _index_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def extract_speaker_embedding(
    audio_path: str | Path,
    segments: list[DiarSegment],
    speaker_label: str,
    cfg: dict[str, Any],
) -> Any:
    """Extract a duration-weighted centroid embedding for a speaker.

    Collects all segments for ``speaker_label``, extracts embeddings from each,
    and returns a weighted average (by segment duration).
    """
    import numpy as np
    import torch
    import torchaudio

    encoder = _get_encoder(cfg)

    speaker_segs = [s for s in segments if s.speaker == speaker_label]
    if not speaker_segs:
        raise ValueError(f"No segments found for speaker {speaker_label}")

    waveform, sample_rate = torchaudio.load(str(audio_path))
    # Convert to mono if needed
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    embeddings: list[np.ndarray] = []
    weights: list[float] = []

    for seg in speaker_segs:
        start_sample = int(seg.start_sec * sample_rate)
        end_sample = int(seg.end_sec * sample_rate)
        chunk = waveform[:, start_sample:end_sample]

        duration = seg.end_sec - seg.start_sec
        if duration < 0.5:
            continue  # Skip very short segments

        with torch.no_grad():
            emb = encoder.encode_batch(chunk).squeeze().cpu().numpy()
        embeddings.append(emb)
        weights.append(duration)

    if not embeddings:
        raise ValueError(f"No usable segments (>0.5s) for speaker {speaker_label}")

    # Duration-weighted centroid
    weights_arr = np.array(weights)
    weights_arr /= weights_arr.sum()
    centroid = np.average(embeddings, axis=0, weights=weights_arr)

    # L2-normalize
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm

    return centroid


def enroll(
    name: str,
    embedding: Any,
    cfg: dict[str, Any],
    source: str = "manual",
) -> Path:
    """Save a voiceprint embedding for a person.

    Returns the path to the saved .npy file.
    """
    import numpy as np
    from datetime import datetime

    vp_dir = _voiceprints_dir(cfg)
    vp_dir.mkdir(parents=True, exist_ok=True)

    index = _load_index(cfg)
    entries = index.get(name, [])
    n = len(entries)
    filename = f"{name}_{n:03d}.npy"
    filepath = vp_dir / filename

    np.save(str(filepath), embedding)

    entries.append({
        "file": filename,
        "source": source,
        "enrolled_at": datetime.now().isoformat(),
    })
    index[name] = entries
    _save_index(cfg, index)

    ui.ok(f"Voiceprint enrolled: {name} ({filename})")
    return filepath


def _load_all_voiceprints(cfg: dict[str, Any]) -> dict[str, Any]:
    """Load all voiceprints as {name: averaged_embedding}."""
    import numpy as np

    index = _load_index(cfg)
    vp_dir = _voiceprints_dir(cfg)
    result: dict[str, Any] = {}

    for name, entries in index.items():
        embeddings = []
        for entry in entries:
            path = vp_dir / entry["file"]
            if path.exists():
                embeddings.append(np.load(str(path)))
        if embeddings:
            avg = np.mean(embeddings, axis=0)
            norm = np.linalg.norm(avg)
            if norm > 0:
                avg = avg / norm
            result[name] = avg

    return result


def match_speakers(
    audio_path: str | Path,
    segments: list[DiarSegment],
    cfg: dict[str, Any],
) -> dict[str, VoiceprintMatch | None]:
    """Match each detected speaker against enrolled voiceprints.

    Returns ``{speaker_label: VoiceprintMatch | None}``.
    """
    threshold = cfg.get("voiceprint_threshold", 0.65)

    # Check index before loading numpy / voiceprint files
    index = _load_index(cfg)
    if not index:
        ui.muted("No voiceprints enrolled — skipping voiceprint matching")
        unique_speakers = sorted({s.speaker for s in segments})
        return {spk: None for spk in unique_speakers}

    enrolled = _load_all_voiceprints(cfg)
    if not enrolled:
        ui.muted("No voiceprints enrolled — skipping voiceprint matching")
        unique_speakers = sorted({s.speaker for s in segments})
        return {spk: None for spk in unique_speakers}

    import numpy as np

    unique_speakers = sorted({s.speaker for s in segments})
    matches: dict[str, VoiceprintMatch | None] = {}

    for speaker_label in unique_speakers:
        try:
            emb = extract_speaker_embedding(audio_path, segments, speaker_label, cfg)
        except ValueError:
            matches[speaker_label] = None
            continue

        best_name: Optional[str] = None
        best_score = -1.0

        for name, ref_emb in enrolled.items():
            score = float(np.dot(emb, ref_emb))
            if score > best_score:
                best_score = score
                best_name = name

        if best_name is not None and best_score > 0:
            confident = best_score >= threshold
            matches[speaker_label] = VoiceprintMatch(
                name=best_name,
                score=best_score,
                confident=confident,
            )
            conf_str = "confident" if confident else "low confidence"
            ui.label_value(
                speaker_label,
                f"{best_name} (score={best_score:.3f}, {conf_str})",
            )
        else:
            matches[speaker_label] = None

    return matches


def enroll_from_conversation(
    audio_path: str | Path,
    segments: list[DiarSegment],
    speaker_label: str,
    name: str,
    cfg: dict[str, Any],
) -> None:
    """Auto-learn a voiceprint from a confirmed speaker in a conversation."""
    if not cfg.get("auto_learn_voiceprints", True):
        return

    try:
        emb = extract_speaker_embedding(audio_path, segments, speaker_label, cfg)
        enroll(name, emb, cfg, source="auto-learn")
    except Exception as e:
        ui.warn(f"Could not auto-learn voiceprint for {name}: {e}")
