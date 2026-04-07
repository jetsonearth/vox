"""FastAPI sidecar for the Vox notch app.

Wraps the existing vox pipeline as HTTP endpoints so the Swift UI
can drive recording, transcription, diarization, speaker identification,
and analysis without touching the CLI.

Run with: uv run vox-server [--port PORT]
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import config as c
from . import naming
from .recorder import RecordingSession, check_ffmpeg, convert_to_m4a

app = FastAPI(title="Vox Server", version="0.1.0")

# ---------------------------------------------------------------------------
# In-memory state (single-user app, one session at a time)
# ---------------------------------------------------------------------------

_recording: RecordingSession | None = None
_jobs: dict[str, dict[str, Any]] = {}  # job_id -> {status, result, error}

# Cache pipeline results between steps so the user can configure before finalizing
_session_cache: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RecordStatusResponse(BaseModel):
    recording: bool
    elapsed: float


class TranscribeRequest(BaseModel):
    audio_path: str
    language_hints: list[str] = ["en", "zh"]
    context: str | None = None
    enable_diarization: bool = True
    num_speakers: int | None = None


class FinalizeRequest(BaseModel):
    audio_path: str
    transcript: str
    session_name: str
    speaker_mapping: dict[str, str] = {}  # {"SPEAKER_00": "Jetson", ...}
    people: list[str] = []
    language_hints: list[str] = ["en", "zh"]
    date_override: str | None = None  # ISO date string
    is_solo: bool = False
    topic: str = ""


class SpeakerClipRequest(BaseModel):
    audio_path: str
    start_sec: float
    end_sec: float


# ---------------------------------------------------------------------------
# Recording endpoints
# ---------------------------------------------------------------------------


@app.post("/record/start")
async def record_start():
    global _recording
    if _recording and _recording.is_recording:
        raise HTTPException(400, "Already recording")
    _recording = RecordingSession()
    _recording.start()
    return {"status": "recording"}


@app.post("/record/stop")
async def record_stop():
    global _recording
    if not _recording or not _recording.is_recording:
        raise HTTPException(400, "Not recording")
    wav_path = _recording.stop()
    elapsed = _recording.elapsed

    # Convert to M4A in background-safe way
    if check_ffmpeg():
        m4a_path = convert_to_m4a(wav_path)
        audio_path = str(m4a_path)
    else:
        audio_path = str(wav_path)

    _recording = None
    return {"audio_path": audio_path, "elapsed": round(elapsed, 1)}


@app.post("/record/abort")
async def record_abort():
    global _recording
    if _recording:
        _recording.abort()
        _recording = None
    return {"status": "aborted"}


@app.get("/record/status")
async def record_status():
    if _recording and _recording.is_recording:
        return RecordStatusResponse(recording=True, elapsed=_recording.elapsed)
    return RecordStatusResponse(recording=False, elapsed=0.0)


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------


@app.post("/pipeline/transcribe")
async def pipeline_transcribe(req: TranscribeRequest, background_tasks: BackgroundTasks):
    """Start transcription + diarization as a background job. Returns job_id to poll."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"status": "running", "result": None, "error": None}
    background_tasks.add_task(_run_transcribe, job_id, req)
    return {"job_id": job_id}


def _run_transcribe(job_id: str, req: TranscribeRequest) -> None:
    """Background task: transcribe + optionally diarize."""
    try:
        cfg = c.load_config()
        c.ensure_dirs(cfg)

        from .transcriber import transcribe

        # Use pyannote if available and enabled in config, otherwise fall back to Soniox diarization
        use_pyannote = req.enable_diarization and cfg.get("enable_diarization", False)

        result = transcribe(
            req.audio_path,
            cfg,
            language_hints=req.language_hints,
            context=req.context,
            # Only disable Soniox diarization if pyannote will handle it
            enable_soniox_diarization=not use_pyannote,
        )

        transcript = result.text
        import logging
        logging.info(f"[transcribe] transcript length: {len(transcript)}, use_pyannote: {use_pyannote}")
        segments_data: list[dict] = []
        speaker_previews: list[dict] = []

        # Extract Soniox speaker labels if present (Speaker 1, Speaker 2, etc.)
        if not use_pyannote:
            from .speaker import extract_speakers, get_preview
            soniox_speakers = extract_speakers(transcript)
            if soniox_speakers:
                speaker_previews = [
                    {
                        "label": label,
                        "text_snippet": get_preview(transcript, label, max_sentences=2)[:200],
                        "best_segment_start_sec": 0.0,
                        "best_segment_end_sec": 5.0,
                    }
                    for label in soniox_speakers
                ]
                logging.info(f"[transcribe] Soniox speakers found: {soniox_speakers}")

        if use_pyannote:
            try:
                from .align import align_tokens_to_segments, render_aligned_tokens
                from .diarize import diarize
                from .speaker import get_speaker_previews
                from .voiceprint import match_speakers

                num_spk = req.num_speakers
                segments = diarize(req.audio_path, cfg, num_speakers=num_spk)

                # Align tokens to diarization segments
                aligned = align_tokens_to_segments(result.tokens, segments)
                transcript = render_aligned_tokens(aligned)

                # Segment data for the client
                segments_data = [
                    {
                        "start_sec": s.start_sec,
                        "end_sec": s.end_sec,
                        "speaker": s.speaker,
                    }
                    for s in segments
                ]

                # Speaker previews for flashcard UI
                previews = get_speaker_previews(transcript, segments)
                speaker_previews = [
                    {
                        "label": p.label,
                        "text_snippet": p.text_snippet,
                        "best_segment_start_sec": p.best_segment_start_sec,
                        "best_segment_end_sec": p.best_segment_end_sec,
                    }
                    for p in previews
                ]

                # Voiceprint matching
                vp_matches_raw = match_speakers(req.audio_path, segments, cfg)
                vp_matches = {}
                for label, match in vp_matches_raw.items():
                    if match is not None:
                        vp_matches[label] = {
                            "name": match.name,
                            "score": match.score,
                            "confident": match.confident,
                        }
                    else:
                        vp_matches[label] = None

                # Cache segments for later audio clip extraction
                _session_cache[job_id] = {
                    "segments": segments,
                    "audio_path": req.audio_path,
                }

            except RuntimeError:
                # Diarization not available, fall back to Soniox
                vp_matches = {}
        else:
            vp_matches = {}

        _jobs[job_id] = {
            "status": "completed",
            "result": {
                "transcript": transcript,
                "segments": segments_data,
                "speaker_previews": speaker_previews,
                "voiceprint_matches": vp_matches,
            },
            "error": None,
        }
    except Exception as e:
        _jobs[job_id] = {
            "status": "failed",
            "result": None,
            "error": str(e),
        }


@app.get("/pipeline/status/{job_id}")
async def pipeline_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, f"Job {job_id} not found")
    return _jobs[job_id]


@app.post("/pipeline/finalize")
async def pipeline_finalize(req: FinalizeRequest, background_tasks: BackgroundTasks):
    """Apply speaker mapping, run analysis, create Obsidian notes."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"status": "running", "result": None, "error": None}
    background_tasks.add_task(_run_finalize, job_id, req)
    return {"job_id": job_id}


def _run_finalize(job_id: str, req: FinalizeRequest) -> None:
    try:
        cfg = c.load_config()
        c.ensure_dirs(cfg)

        from .analyzer import analyze
        from .hooks import run_hook
        from .obsidian import (
            append_to_conversations_section,
            create_conversation_note,
            ensure_daily_note,
            save_transcript,
        )
        from .speaker import apply_speaker_mapping

        transcript = req.transcript
        import logging
        logging.info(f"[finalize] transcript length: {len(transcript)}, mapping: {req.speaker_mapping}")

        # Apply speaker mapping from the UI (user tagged speakers via flashcard)
        if req.speaker_mapping:
            transcript = apply_speaker_mapping(transcript, req.speaker_mapping)

        # Auto-learn voiceprints from confirmed mappings
        cached = _session_cache.get(job_id)
        if cached and req.speaker_mapping:
            try:
                from .voiceprint import enroll_from_conversation

                for label, name in req.speaker_mapping.items():
                    enroll_from_conversation(
                        cached["audio_path"],
                        cached["segments"],
                        label,
                        name,
                        cfg,
                    )
            except Exception:
                pass  # Non-fatal

        # Determine date
        if req.date_override:
            today = date.fromisoformat(req.date_override)
        else:
            today = date.today()

        slug = naming.make_slug(req.session_name)

        # Archive audio
        audio_path = Path(req.audio_path)
        audio_dest = (
            c.audio_archive(cfg)
            / naming.make_archive_subdir(today)
            / naming.make_audio_filename(today, slug)
        )
        audio_dest.parent.mkdir(parents=True, exist_ok=True)
        if audio_path.resolve() != audio_dest.resolve():
            import shutil
            shutil.move(str(audio_path), audio_dest)

        # Save transcript
        transcript_filename = save_transcript(today, slug, transcript, cfg, announce=False)

        # Analysis
        analysis = analyze(transcript)

        # Create conversation note (non-interactive - always overwrite)
        note_path = _create_note_noninteractive(
            today, req.session_name, req.people, transcript_filename,
            analysis, cfg, req.topic,
        )

        # Daily note
        daily_path = ensure_daily_note(today, cfg)
        note_title = naming.make_note_title(today, req.session_name)
        append_to_conversations_section(daily_path, note_title)

        # Post-process hook
        transcript_path = c.transcripts_dir(cfg) / transcript_filename
        run_hook(cfg, today, req.people, note_path, audio_dest, transcript_path)

        _jobs[job_id] = {
            "status": "completed",
            "result": {
                "note_path": str(note_path),
                "transcript_path": str(c.transcripts_dir(cfg) / transcript_filename),
                "audio_path": str(audio_dest),
                "analysis_ok": analysis is not None,
            },
            "error": None,
        }
    except Exception as e:
        _jobs[job_id] = {
            "status": "failed",
            "result": None,
            "error": str(e),
        }


def _create_note_noninteractive(
    d: date,
    display_name: str,
    people: list[str],
    transcript_filename: str,
    analysis: str | None,
    cfg: dict[str, Any],
    topic: str = "",
) -> Path:
    """Create conversation note without interactive prompts (always overwrite)."""
    from .obsidian import build_frontmatter

    note_title = naming.make_note_title(d, display_name)
    note_path = c.conversations_dir(cfg) / f"{note_title}.md"

    frontmatter = build_frontmatter(d, people, topic)
    body_parts = [
        frontmatter,
        "# Transcript",
        "",
        f"[[Transcripts/{transcript_filename}]]",
        "",
        "---",
        "",
        "# Analysis",
        "",
    ]
    if analysis:
        body_parts.append(analysis.lstrip("\n"))
    else:
        body_parts.append("*(Run analysis to populate this section)*")
    body_parts.append("")

    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("\n".join(body_parts), encoding="utf-8")
    return note_path


# ---------------------------------------------------------------------------
# Speaker audio clip endpoint
# ---------------------------------------------------------------------------


@app.post("/speakers/clip")
async def speaker_audio_clip(req: SpeakerClipRequest):
    """Extract and serve a short audio clip for a speaker (for flashcard UI)."""
    audio_path = Path(req.audio_path)
    if not audio_path.exists():
        raise HTTPException(404, f"Audio file not found: {req.audio_path}")

    # Use ffmpeg to extract the clip
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    duration = req.end_sec - req.start_sec

    try:
        subprocess.run(
            [
                "ffmpeg", "-i", str(audio_path),
                "-ss", str(req.start_sec),
                "-t", str(duration),
                "-c:a", "pcm_s16le",
                "-ar", "44100",
                "-ac", "1",
                "-y", tmp.name,
            ],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        Path(tmp.name).unlink(missing_ok=True)
        raise HTTPException(500, f"Failed to extract audio clip: {e}")

    return FileResponse(
        tmp.name,
        media_type="audio/wav",
        filename="speaker_clip.wav",
    )


# ---------------------------------------------------------------------------
# Health / info
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/config")
async def get_config():
    """Return non-sensitive config values useful for the UI."""
    cfg = c.load_config()
    return {
        "user_name": cfg.get("user_name", "Me"),
        "language_hints": cfg.get("language_hints", ["en", "zh"]),
        "enable_diarization": cfg.get("enable_diarization", False),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(prog="vox-server")
    parser.add_argument("--port", type=int, default=7483)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
