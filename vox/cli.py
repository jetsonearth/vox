"""Entry point, argparse, and pipeline orchestration."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import config as c
from . import naming
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
from .speaker import confirm_speakers
from .transcriber import transcribe


def _print_dependency_status() -> None:
    print(f"  sox: {'OK' if check_sox() else 'MISSING'}")
    print(f"  ffmpeg: {'OK' if shutil.which('ffmpeg') else 'MISSING — WAV fallback if sox only'}")
    print(f"  codex: {'OK' if shutil.which('codex') else 'MISSING — analysis will be skipped'}")


def _try_brew_install_recording_deps() -> None:
    """On macOS, install sox / ffmpeg via Homebrew when missing."""
    if platform.system() != "Darwin":
        return
    brew = shutil.which("brew")
    if not brew:
        print("  Homebrew not in PATH — install from https://brew.sh then run: brew install sox")
        return

    need: list[str] = []
    if not check_sox():
        need.append("sox")
    if not shutil.which("ffmpeg"):
        need.append("ffmpeg")
    if not need:
        return

    print(f"\nInstalling missing tools via Homebrew ({', '.join(need)}) …")
    try:
        subprocess.run([brew, "install", *need], check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"  brew install failed ({e}). Run manually: brew install {' '.join(need)}")
        return

    if check_sox():
        print("  sox: OK")
    else:
        print("  sox: still missing — try: brew install sox")
    if shutil.which("ffmpeg"):
        print("  ffmpeg: OK")
    elif "ffmpeg" in need:
        print("  ffmpeg: still missing — try: brew install ffmpeg")


def cmd_init(args: argparse.Namespace) -> None:
    """Interactive setup wizard."""
    print("=== Vox Setup ===\n")

    cfg = c.load_config()

    cfg["user_name"] = input(f"Your name [{cfg['user_name']}]: ").strip() or cfg["user_name"]

    vault = input(f"Obsidian vault path [{cfg['vault_path']}]: ").strip()
    if vault:
        cfg["vault_path"] = vault

    api_key = input(f"Soniox API key [{'***' + cfg['soniox_api_key'][-4:] if cfg['soniox_api_key'] else 'not set'}]: ").strip()
    if api_key:
        cfg["soniox_api_key"] = api_key

    # Check dependencies; on macOS + Homebrew, install sox/ffmpeg when missing
    print("\nChecking dependencies:")
    _try_brew_install_recording_deps()
    _print_dependency_status()

    c.save_config(cfg)
    c.ensure_dirs(cfg)

    print(f"\nConfig saved to: {c.CONFIG_FILE}")
    print(f"Audio archive: {c.audio_archive(cfg)}")
    print(f"Vault: {c.vault_path(cfg)}")
    print("\nReady! Try: vox record <name>")


def cmd_record(args: argparse.Namespace) -> None:
    """Record audio and run the full pipeline."""
    cfg = c.load_config()
    c.ensure_dirs(cfg)
    today = date.today()

    # Determine topic and speakers
    topic = args.topic
    is_solo = args.solo

    if is_solo:
        # Solo brain dump — no people card
        display_name = topic or "Brain Dump"
        people: list[str] = []
        speaker_names = [cfg.get("user_name", "Me")]
    else:
        # Parse speakers
        if args.speakers:
            raw_names = [s.strip() for s in args.speakers.split(",")]
        elif topic:
            # topic is the person's name in simple case: vox record terry
            raw_names = [topic]
            topic = ""
        else:
            print("Error: provide a name or use --solo")
            sys.exit(1)

        people = resolve_people(raw_names, cfg)
        speaker_names = [cfg.get("user_name", "Me")] + people

        # Build display name
        if topic:
            display_name = topic
        else:
            display_name = " ".join(people)

    slug = naming.make_slug(display_name)

    # Step 1: Record
    print(f"\n--- Recording: {display_name} ---\n")
    audio_dest = (
        c.audio_archive(cfg)
        / naming.make_archive_subdir(today)
        / naming.make_audio_filename(today, slug)
    )
    audio_path = record(output_path=audio_dest)

    # Run the rest of the pipeline
    _run_pipeline(cfg, today, audio_path, display_name, slug, people, speaker_names, topic, is_solo)


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
            print(f"Warning: could not parse --date '{date_override}', using file date.")

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


def cmd_process(args: argparse.Namespace) -> None:
    """Process an existing audio file through the pipeline."""
    cfg = c.load_config()
    c.ensure_dirs(cfg)

    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        print(f"Error: file not found: {audio_path}")
        sys.exit(1)

    today = _infer_date(audio_path, getattr(args, "date", None))
    print(f"  Recording date: {today.isoformat()}")

    # Parse speakers
    if args.speaker:
        raw_names = [s.strip() for s in args.speaker.split(",")]
        people = resolve_people(raw_names, cfg)
    else:
        people = []

    is_solo = not people
    speaker_names = [cfg.get("user_name", "Me")] + people if people else [cfg.get("user_name", "Me")]

    topic = args.topic or ""
    if people and not topic:
        display_name = " ".join(people)
    elif topic:
        display_name = topic
    else:
        display_name = audio_path.stem

    slug = naming.make_slug(display_name)

    # Archive the audio
    audio_dest = (
        c.audio_archive(cfg)
        / naming.make_archive_subdir(today)
        / naming.make_audio_filename(today, slug)
    )
    audio_dest.parent.mkdir(parents=True, exist_ok=True)
    if audio_path != audio_dest:
        shutil.copy2(audio_path, audio_dest)
        print(f"  Audio archived: {audio_dest}")

    _run_pipeline(cfg, today, audio_dest, display_name, slug, people, speaker_names, topic, is_solo)


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
) -> None:
    """Run steps 2-8 of the pipeline after audio is ready."""

    # Step 2: Transcribe
    print("\n--- Transcribing ---\n")
    try:
        transcript = transcribe(str(audio_path), cfg)
    except Exception as e:
        print(f"\nTranscription failed: {e}")
        print(f"Audio is saved at: {audio_path}")
        print("Retry with: vox process", audio_path)
        sys.exit(1)

    # Step 3: Speaker confirmation
    print("\n--- Speaker Identification ---")
    transcript = confirm_speakers(transcript, speaker_names)

    # Step 4: Save transcript
    print("\n--- Saving ---\n")
    transcript_filename = save_transcript(today, slug, transcript, cfg)

    # Step 5: Analysis (non-fatal)
    print("\n--- Analysis ---\n")
    analysis = analyze(transcript)

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

    # Summary
    print("\n--- Done ---\n")
    print(f"  Audio:        {audio_path}")
    print(f"  Transcript:   {c.transcripts_dir(cfg) / transcript_filename}")
    print(f"  Note:         {note_path}")
    print(f"  Daily note:   {daily_path}")
    if analysis:
        print("  Analysis:     included")
    else:
        print("  Analysis:     skipped (add manually or re-run)")
    print()


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

    # vox process
    p_process = subparsers.add_parser("process", help="Process an existing audio file")
    p_process.add_argument("audio_file", help="Path to audio file")
    p_process.add_argument("--speaker", help="Comma-separated speaker names")
    p_process.add_argument("--topic", help="Topic or title override")
    p_process.add_argument("--date", help="Recording date (YYYY-MM-DD or M-D-YY). Auto-detected from filename/file metadata if omitted.")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "process":
        cmd_process(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
