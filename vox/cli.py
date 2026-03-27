"""Entry point, argparse, and pipeline orchestration."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import config as c
from . import naming
from . import ui
from .analyzer import analyze
from .contacts import resolve_people
from .hooks import run_hook
from .obsidian import (
    append_to_conversations_section,
    create_conversation_note,
    ensure_daily_note,
    save_transcript,
)
from .recorder import check_sox, record
from .speaker import (
    auto_label_speakers,
    confirm_speakers,
    confirm_speakers_with_voiceprint,
    extract_speakers,
)
from .transcriber import transcribe


def _print_dependency_status() -> None:
    ui.label_value("sox", "OK" if check_sox() else "MISSING")
    ui.label_value(
        "ffmpeg",
        "OK" if shutil.which("ffmpeg") else "MISSING (WAV fallback if sox only)",
    )
    ui.label_value(
        "codex",
        "OK" if shutil.which("codex") else "MISSING — analysis skipped",
    )


def _try_brew_install_recording_deps() -> None:
    """On macOS, install sox / ffmpeg via Homebrew when missing."""
    if platform.system() != "Darwin":
        return
    brew = shutil.which("brew")
    if not brew:
        ui.warn("Homebrew not in PATH — install from https://brew.sh then run: brew install sox")
        return

    need: list[str] = []
    if not check_sox():
        need.append("sox")
    if not shutil.which("ffmpeg"):
        need.append("ffmpeg")
    if not need:
        return

    ui.info(f"Installing via Homebrew: {', '.join(need)} …")
    try:
        subprocess.run([brew, "install", *need], check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        ui.err(f"brew install failed ({e}). Run manually: brew install {' '.join(need)}")
        return

    if check_sox():
        ui.ok("sox installed")
    else:
        ui.warn("sox still missing — try: brew install sox")
    if shutil.which("ffmpeg"):
        ui.ok("ffmpeg installed")
    elif "ffmpeg" in need:
        ui.warn("ffmpeg still missing — try: brew install ffmpeg")


def cmd_init(args: argparse.Namespace) -> None:
    """Interactive setup wizard."""
    ui.init_header()
    ui.get_console().print()

    cfg = c.load_config()

    cfg["user_name"] = input(f"Your name [{cfg['user_name']}]: ").strip() or cfg["user_name"]

    vault = input(f"Obsidian vault path [{cfg['vault_path']}]: ").strip()
    if vault:
        cfg["vault_path"] = vault

    api_key = input(f"Soniox API key [{'***' + cfg['soniox_api_key'][-4:] if cfg['soniox_api_key'] else 'not set'}]: ").strip()
    if api_key:
        cfg["soniox_api_key"] = api_key

    ui.section("Dependencies")
    _try_brew_install_recording_deps()
    _print_dependency_status()

    c.save_config(cfg)
    c.ensure_dirs(cfg)

    ui.get_console().print()
    ui.ok(f"Config saved → {c.CONFIG_FILE}")
    ui.label_value("Audio archive", str(c.audio_archive(cfg)))
    ui.label_value("Vault", str(c.vault_path(cfg)))
    ui.get_console().print()
    ui.banner_subtitle("Ready — try: vox record <name>")


def _extract_date_prefix(raw: str) -> tuple[date, str]:
    """Extract a date from the beginning of a string.

    Supports ``YYYY-M-D``, ``YYYY-MM-DD``, ``M-D-YY``, ``MM-DD-YYYY``.
    Returns ``(parsed_date, remainder)``; falls back to today if no date found.
    """
    raw = raw.strip()
    # YYYY-M-D or YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})\s*(.*)", raw)
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d, m.group(4).strip()
        except ValueError:
            pass
    # M-D-YY or MM-DD-YYYY
    m = re.match(r"(\d{1,2})-(\d{1,2})-(\d{2,4})\s*(.*)", raw)
    if m:
        try:
            year = int(m.group(3))
            if year < 100:
                year += 2000
            d = date(year, int(m.group(1)), int(m.group(2)))
            return d, m.group(4).strip()
        except ValueError:
            pass
    return date.today(), raw


def cmd_record(args: argparse.Namespace) -> None:
    """Record audio and run the full pipeline."""
    cfg = c.load_config()
    c.ensure_dirs(cfg)

    # Extract date prefix from topic arg (defaults to today)
    today, remainder = _extract_date_prefix(args.topic or "")

    is_solo = args.solo

    if is_solo:
        # Solo brain dump — no people card
        display_name = remainder or "Brain Dump"
        people: list[str] = []
        speaker_names = [cfg.get("user_name", "Me")]
    else:
        # Parse speakers
        if args.speakers:
            raw_names = [s.strip() for s in args.speakers.split(",")]
            topic = remainder
        elif remainder:
            # First word = person hint, rest = topic
            parts = remainder.split(None, 1)
            raw_names = [parts[0]]
            topic = parts[1] if len(parts) > 1 else ""
        else:
            ui.err("Provide a name/topic or use --solo")
            sys.exit(1)

        people = resolve_people(raw_names, cfg)
        speaker_names = [cfg.get("user_name", "Me")] + people

        # Build display name: resolved person + topic
        if topic:
            display_name = f"{people[0]} {topic}" if people else topic
        else:
            display_name = " ".join(people)

    slug = naming.make_slug(display_name)

    ui.section(f"Recording — {ui.esc(display_name)}")
    audio_dest = (
        c.audio_archive(cfg)
        / naming.make_archive_subdir(today)
        / naming.make_audio_filename(today, slug)
    )
    audio_path = record(output_path=audio_dest)

    soniox_hints, soniox_context = _prompt_soniox_options(cfg, args)

    _run_pipeline(
        cfg,
        today,
        audio_path,
        display_name,
        slug,
        people,
        speaker_names,
        topic,
        is_solo,
        name_speakers=args.name_speakers,
        no_diarize=getattr(args, "no_diarize", False),
        soniox_language_hints=soniox_hints,
        soniox_context=soniox_context,
    )


def _prompt_soniox_options(
    cfg: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[list[str], str | None]:
    """Language hints + Soniox ``context``: CLI flags, else TTY prompts (``process`` / ``record``)."""
    default_hints = list(cfg.get("language_hints", ["en", "zh"]))
    tty = sys.stdin.isatty()
    flag_lang = args.language_hints
    flag_ctx = args.soniox_context

    if tty and (flag_lang is None or flag_ctx is None):
        ui.section("Transcription options")

    if flag_lang is not None:
        raw = flag_lang.strip()
        hints = [x.strip().lower() for x in raw.split(",") if x.strip()] if raw else list(default_hints)
        if not hints:
            hints = list(default_hints)
    elif tty:
        default_s = ",".join(default_hints)
        line = input(
            f"  Languages in this recording (comma-separated ISO codes, Enter={default_s}): "
        ).strip().lower()
        if line:
            hints = [x.strip() for x in line.split(",") if x.strip()]
            if not hints:
                hints = list(default_hints)
        else:
            hints = list(default_hints)
    else:
        hints = list(default_hints)

    if flag_ctx is not None:
        context = flag_ctx.strip() or None
    elif tty:
        line = input(
            "  Optional Soniox context (topic, names, jargon, acronyms; Enter=skip): "
        ).strip()
        context = line or None
    else:
        context = None

    ctx_note = f"; Soniox context ({len(context)} chars)" if context else ""
    ui.muted(f"language_hints={hints}{ctx_note}")
    return hints, context


def _infer_date(audio_path: Path, date_override: str | None) -> date:
    """Determine the recording date from --date flag, filename, or file creation time."""
    # Explicit override
    if date_override:
        try:
            return date.fromisoformat(date_override)
        except ValueError:
            # Try M-D-YY format
            for fmt in ("%m-%d-%y", "%m-%d-%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(date_override, fmt).date()
                except ValueError:
                    continue
            ui.warn(f"Could not parse --date '{date_override}', using file date.")

    # Try to extract date from filename
    name = audio_path.stem
    # Match YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", name)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # Match M-D-YY or MM-DD-YY at end or with spaces
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{2,4})", name)
    if m:
        try:
            year = int(m.group(3))
            if year < 100:
                year += 2000
            return date(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    # Fall back to file creation time (birthtime on macOS)
    try:
        stat = audio_path.stat()
        # st_birthtime is macOS-specific (file creation time)
        ctime = getattr(stat, "st_birthtime", stat.st_mtime)
        return date.fromtimestamp(ctime)
    except OSError:
        return date.today()


def cmd_analyze(args: argparse.Namespace) -> None:
    """Re-run analysis on an existing transcript and update the conversation note."""
    cfg = c.load_config()

    # Accept either a transcript path or a conversation note path
    target = Path(args.file)
    if not target.exists():
        ui.err(f"File not found: {target}")
        sys.exit(1)

    # Determine transcript path and note path
    transcripts = c.transcripts_dir(cfg)
    conversations = c.conversations_dir(cfg)

    if target.parent.resolve() == transcripts.resolve():
        # Given a transcript file — find the matching note
        transcript_path = target
        # Transcript: 2026-03-25-stash-pomichter.txt → Note: 2026-03-25 Stash Pomichter.md
        stem = transcript_path.stem  # e.g. 2026-03-25-stash-pomichter
        note_path = _find_note_for_transcript(stem, conversations)
    elif target.parent.resolve() == conversations.resolve():
        # Given a conversation note — find the transcript from its content
        note_path = target
        transcript_path = _find_transcript_for_note(target, transcripts)
    else:
        # Try as a raw transcript file
        transcript_path = target
        note_path = None

    if transcript_path is None or not transcript_path.exists():
        ui.err(f"Could not find transcript file")
        sys.exit(1)

    ui.section(f"Analyzing {transcript_path.name}")
    transcript = transcript_path.read_text(encoding="utf-8")

    ui.label_value("Transcript", f"{len(transcript)} chars, {transcript.count(chr(10))} lines")

    t0 = time.monotonic()
    analysis = analyze(transcript)

    if not analysis:
        ui.err("Analysis failed — see errors above")
        sys.exit(1)

    ui.ok("Analysis finished", time.monotonic() - t0)

    # Update the conversation note if we found one
    if note_path and note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        import re as _re
        if "# Analysis" in existing:
            head = existing.split("# Analysis", 1)[0]
        elif "## Analysis" in existing:
            head = existing.split("## Analysis", 1)[0]
        else:
            head = existing
        head = head.rstrip()
        head = _re.sub(r"\n---\s*$", "", head).rstrip()
        note_path.write_text(
            head + "\n\n---\n\n# Analysis\n\n" + analysis.lstrip("\n") + "\n",
            encoding="utf-8",
        )
        ui.ok(f"Note updated → {note_path}")
    else:
        # No note found — print analysis to stdout
        if note_path:
            ui.warn(f"Note not found: {note_path}")
        ui.get_console().print()
        ui.get_console().print(analysis)


def _find_note_for_transcript(transcript_stem: str, conversations_dir: Path) -> Path | None:
    """Find a conversation note matching a transcript stem like '2026-03-25-stash-pomichter'."""
    # Convert slug to title case: 2026-03-25-stash-pomichter → 2026-03-25 Stash Pomichter
    parts = transcript_stem.split("-", 3)  # ['2026', '03', '25', 'stash-pomichter']
    if len(parts) >= 4:
        date_part = f"{parts[0]}-{parts[1]}-{parts[2]}"
        name_slug = parts[3]
        # Try title-cased version
        name_title = " ".join(w.capitalize() for w in name_slug.split("-"))
        candidate = conversations_dir / f"{date_part} {name_title}.md"
        if candidate.exists():
            return candidate
    # Fallback: glob for files starting with the date
    if len(parts) >= 3:
        date_part = f"{parts[0]}-{parts[1]}-{parts[2]}"
        matches = list(conversations_dir.glob(f"{date_part}*.md"))
        if len(matches) == 1:
            return matches[0]
    return None


def _find_transcript_for_note(note_path: Path, transcripts_dir: Path) -> Path | None:
    """Find the transcript file referenced in a conversation note."""
    content = note_path.read_text(encoding="utf-8")
    # Look for [[Transcripts/filename.txt]] wikilink
    import re as _re
    m = _re.search(r"\[\[Transcripts/([^\]]+)\]\]", content)
    if m:
        candidate = transcripts_dir / m.group(1)
        if candidate.exists():
            return candidate
    # Fallback: match by date prefix from note filename
    # Note: 2026-03-25 Stash Pomichter.md → look for 2026-03-25-*.txt
    stem = note_path.stem  # "2026-03-25 Stash Pomichter"
    date_part = stem[:10]  # "2026-03-25"
    matches = list(transcripts_dir.glob(f"{date_part}*"))
    if len(matches) == 1:
        return matches[0]
    return None


def cmd_enroll(args: argparse.Namespace) -> None:
    """Enroll a voiceprint from an audio file."""
    cfg = c.load_config()
    c.ensure_dirs(cfg)

    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        ui.err(f"File not found: {audio_path}")
        sys.exit(1)

    try:
        from .diarize import diarize
        from .voiceprint import enroll, extract_speaker_embedding
    except RuntimeError as e:
        ui.err(str(e))
        sys.exit(1)

    ui.section(f"Enrolling voiceprint for {ui.esc(args.name)}")

    # Diarize to find speaker segments
    segments = diarize(audio_path, cfg)
    unique_speakers = sorted({s.speaker for s in segments})

    if args.speaker:
        speaker_label = args.speaker
        if speaker_label not in unique_speakers:
            ui.err(f"Speaker '{speaker_label}' not found. Available: {', '.join(unique_speakers)}")
            sys.exit(1)
    elif len(unique_speakers) == 1:
        speaker_label = unique_speakers[0]
        ui.muted(f"Single speaker detected: {speaker_label}")
    else:
        ui.info(f"Multiple speakers detected: {', '.join(unique_speakers)}")
        speaker_label = input(f"  Which speaker is {args.name}? [{unique_speakers[0]}]: ").strip()
        if not speaker_label:
            speaker_label = unique_speakers[0]

    embedding = extract_speaker_embedding(audio_path, segments, speaker_label, cfg)
    filepath = enroll(args.name, embedding, cfg, source="manual")
    ui.ok(f"Voiceprint saved → {filepath}")


def cmd_process(args: argparse.Namespace) -> None:
    """Process an existing audio file through the pipeline."""
    cfg = c.load_config()
    c.ensure_dirs(cfg)

    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        ui.err(f"File not found: {audio_path}")
        sys.exit(1)

    today = _infer_date(audio_path, getattr(args, "date", None))
    ui.label_value("Recording date", today.isoformat())

    # Parse speakers
    if args.speaker:
        raw_names = [s.strip() for s in args.speaker.split(",")]
        people = resolve_people(raw_names, cfg)
    else:
        people = []

    is_solo = not people
    speaker_names = [cfg.get("user_name", "Me")] + people if people else [cfg.get("user_name", "Me")]

    topic = args.topic or ""
    # Title / slug / archive name: explicit --topic, else keep the source file stem.
    # --speaker only affects PRM people + speaker hints, not the filename.
    display_name = topic if topic else audio_path.stem

    slug = naming.make_slug(display_name)
    # Avoid 2026-03-22-2026-03-22-… when the file stem already starts with that date
    if not topic:
        d = today.isoformat()
        if slug.startswith(f"{d}-"):
            shortened = slug[len(d) + 1 :]
            if shortened:
                slug = shortened

    # Archive the audio
    audio_dest = (
        c.audio_archive(cfg)
        / naming.make_archive_subdir(today)
        / naming.make_audio_filename(today, slug)
    )
    audio_dest.parent.mkdir(parents=True, exist_ok=True)
    if audio_path.resolve() != audio_dest.resolve():
        shutil.move(str(audio_path), audio_dest)
        ui.ok(f"Audio moved → {audio_dest}")
    else:
        ui.muted("Audio already in archive")

    soniox_hints, soniox_context = _prompt_soniox_options(cfg, args)

    _run_pipeline(
        cfg,
        today,
        audio_dest,
        display_name,
        slug,
        people,
        speaker_names,
        topic,
        is_solo,
        name_speakers=args.name_speakers,
        no_diarize=getattr(args, "no_diarize", False),
        soniox_language_hints=soniox_hints,
        soniox_context=soniox_context,
    )


def _run_pipeline(
    cfg: dict[str, Any],
    today: date,
    audio_path: Path,
    display_name: str,
    slug: str,
    people: list[str],
    speaker_names: list[str],
    topic: str,
    is_solo: bool,
    *,
    name_speakers: bool = False,
    no_diarize: bool = False,
    soniox_language_hints: list[str] | None = None,
    soniox_context: str | None = None,
) -> None:
    """Run steps 2-8 of the pipeline after audio is ready."""
    pipeline_t0 = time.monotonic()

    use_pyannote = cfg.get("enable_diarization", False) and not no_diarize

    # Step 2: Transcribe
    ui.section("Transcribing")
    try:
        result = transcribe(
            str(audio_path),
            cfg,
            language_hints=soniox_language_hints,
            context=soniox_context,
            enable_soniox_diarization=not use_pyannote,
        )
        transcript = result.text
    except Exception as e:
        ui.get_console().print()
        ui.err(f"Transcription failed: {e}")
        ui.muted(f"Audio: {audio_path}")
        ui.info(f"Retry: vox process {audio_path}")
        sys.exit(1)

    # Step 2b: pyannote diarization + alignment + voiceprint matching
    diar_segments = None
    vp_matches: dict | None = None

    if use_pyannote:
        try:
            from .align import align_tokens_to_segments, render_aligned_tokens
            from .diarize import diarize
            from .voiceprint import enroll_from_conversation, match_speakers

            ui.section("Speaker diarization (pyannote)")
            num_spk = len(speaker_names) if speaker_names else None
            diar_segments = diarize(
                audio_path, cfg,
                num_speakers=num_spk if not is_solo else 1,
            )

            # Align tokens to diarization segments
            ui.muted("Aligning tokens to speaker segments…")
            aligned = align_tokens_to_segments(result.tokens, diar_segments)
            transcript = render_aligned_tokens(aligned)

            # Voiceprint matching
            ui.section("Voiceprint matching")
            vp_matches = match_speakers(audio_path, diar_segments, cfg)

            # Auto-label confident matches
            all_confident = vp_matches and all(
                m is not None and m.confident for m in vp_matches.values()
            )
            if all_confident:
                transcript, mapping = auto_label_speakers(transcript, vp_matches)
                ui.ok(f"All speakers auto-identified: {', '.join(mapping.values())}")
            elif vp_matches and sys.stdin.isatty():
                transcript, mapping = confirm_speakers_with_voiceprint(
                    transcript, vp_matches, speaker_names,
                )
                # Auto-learn voiceprints from confirmed labels
                for label, name in mapping.items():
                    enroll_from_conversation(audio_path, diar_segments, label, name, cfg)
            else:
                ui.muted("No voiceprint matches — keeping diarization labels")
        except RuntimeError as e:
            ui.warn(f"Diarization failed, falling back to Soniox: {e}")
            use_pyannote = False

    # Step 3: Save transcript immediately
    ui.section("Saving transcript")
    transcript_filename = save_transcript(today, slug, transcript, cfg)

    # Step 4: Optional speaker renaming (Soniox fallback path, off by default)
    if not use_pyannote and name_speakers and extract_speakers(transcript):
        ui.section("Speaker identification")
        if not sys.stdin.isatty():
            ui.muted("Not a TTY — keeping Soniox labels (cannot prompt for names).")
        else:
            try:
                from rich.prompt import Confirm

                do_map = Confirm.ask(
                    "Map speakers to names?",
                    default=True,
                    console=ui.get_console(),
                )
            except EOFError:
                do_map = True
            if not do_map:
                ui.muted("Keeping Soniox labels (Speaker 1, 2, …).")
            else:
                transcript = confirm_speakers(transcript, speaker_names)
                save_transcript(today, slug, transcript, cfg, announce=False)
                ui.ok("Transcript updated with speaker names")

    # Step 5: Analysis (non-fatal)
    ui.section("Analysis")
    t0 = time.monotonic()
    analysis = analyze(transcript)
    if analysis:
        ui.ok("Analysis finished", time.monotonic() - t0)
    else:
        ui.warn(f"Analysis skipped ({ui.format_elapsed(time.monotonic() - t0)})")

    # Step 6: Create conversation note
    note_path = create_conversation_note(
        d=today,
        display_name=display_name,
        people=people,
        transcript_filename=transcript_filename,
        analysis=analysis,
        cfg=cfg,
        topic=topic,
    )

    # Step 7: Daily note
    daily_path = ensure_daily_note(today, cfg)
    note_title = naming.make_note_title(today, display_name)
    append_to_conversations_section(daily_path, note_title)

    # Step 8: Post-process hook
    transcript_path = c.transcripts_dir(cfg) / transcript_filename
    run_hook(cfg, today, people, note_path, audio_path, transcript_path)

    total_elapsed = time.monotonic() - pipeline_t0
    ui.panel_done(
        "Done",
        [
            ("Audio", str(audio_path)),
            ("Transcript", str(c.transcripts_dir(cfg) / transcript_filename)),
            ("Note", str(note_path)),
            ("Daily note", str(daily_path)),
        ],
        analysis_ok=bool(analysis),
        total_elapsed=total_elapsed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vox",
        description="Voice recording pipeline automation",
    )
    subparsers = parser.add_subparsers(dest="command")

    # vox init
    subparsers.add_parser("init", help="Setup wizard")

    # vox record
    p_record = subparsers.add_parser("record", help="Record and process a conversation")
    p_record.add_argument("topic", nargs="?", default="", help="Person name or topic")
    p_record.add_argument("--speakers", help="Comma-separated speaker names (e.g. terry,tuo,huey)")
    p_record.add_argument("--solo", action="store_true", help="Brain dump mode (no people card)")
    p_record.add_argument(
        "--name-speakers",
        action="store_true",
        help="After transcription, optionally map Speaker 1, 2, … to names (default: keep Soniox labels)",
    )
    p_record.add_argument(
        "--language-hints",
        default=None,
        metavar="CODES",
        help="Soniox languages (comma-separated ISO codes). Skips prompt after recording.",
    )
    p_record.add_argument(
        "--soniox-context",
        default=None,
        metavar="TEXT",
        help="Soniox context string. Skips prompt after recording.",
    )
    p_record.add_argument(
        "--no-diarize",
        action="store_true",
        help="Disable pyannote diarization, fall back to Soniox speaker labels",
    )

    # vox process
    p_process = subparsers.add_parser("process", help="Process an existing audio file")
    p_process.add_argument("audio_file", help="Path to audio file")
    p_process.add_argument("--speaker", help="Comma-separated speaker names")
    p_process.add_argument("--topic", help="Topic or title override")
    p_process.add_argument("--date", help="Recording date (YYYY-MM-DD or M-D-YY). Auto-detected from filename/file metadata if omitted.")
    p_process.add_argument(
        "--name-speakers",
        action="store_true",
        help="After transcription, optionally map Speaker 1, 2, … to names (default: keep Soniox labels)",
    )
    p_process.add_argument(
        "--language-hints",
        default=None,
        metavar="CODES",
        help="Soniox expected languages (comma-separated ISO codes, e.g. en,zh). Skips language prompt.",
    )
    p_process.add_argument(
        "--soniox-context",
        default=None,
        metavar="TEXT",
        help="Soniox context string (domain, names, jargon). Skips context prompt. See Soniox create_transcription API.",
    )
    p_process.add_argument(
        "--no-diarize",
        action="store_true",
        help="Disable pyannote diarization, fall back to Soniox speaker labels",
    )

    # vox analyze
    p_analyze = subparsers.add_parser("analyze", help="Re-run analysis on an existing transcript")
    p_analyze.add_argument("file", help="Path to transcript (.txt) or conversation note (.md)")

    # vox enroll
    p_enroll = subparsers.add_parser("enroll", help="Enroll a voiceprint from an audio file")
    p_enroll.add_argument("name", help="Person name to enroll")
    p_enroll.add_argument("audio_file", help="Path to audio file containing their voice")
    p_enroll.add_argument(
        "--speaker",
        default=None,
        help="Speaker label to enroll (e.g. SPEAKER_00). Auto-detects if only one speaker.",
    )

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "process":
        cmd_process(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "enroll":
        cmd_enroll(args)
    else:
        ui.get_console().print("[bold cyan]vox[/] [dim]· voice → Obsidian[/]\n")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
