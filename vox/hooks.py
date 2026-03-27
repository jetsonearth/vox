"""Post-process hook runner."""

from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from . import ui


def run_hook(
    cfg: dict[str, Any],
    d: date,
    people: list[str],
    note_path: Path,
    audio_path: Path,
    transcript_path: Path | None = None,
) -> None:
    """Run the optional post-process hook with environment variables."""
    hook = cfg.get("post_process_hook", "")
    if not hook:
        return

    hook_path = Path(hook).expanduser()
    if not hook_path.exists():
        ui.warn(f"Hook not found: {hook_path} — skipping.")
        return

    env = os.environ.copy()
    env["VOX_DATE"] = d.isoformat()
    env["VOX_PEOPLE"] = ",".join(people)
    env["VOX_NOTE_PATH"] = str(note_path)
    env["VOX_AUDIO_PATH"] = str(audio_path)
    if transcript_path:
        env["VOX_TRANSCRIPT_PATH"] = str(transcript_path)

    ui.info(f"Running hook: {hook_path}")
    try:
        result = subprocess.run(
            [str(hook_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout.strip():
            ui.muted(f"Hook stdout: {result.stdout.strip()}")
        if result.returncode != 0:
            ui.warn(f"Hook exited with code {result.returncode}")
            if result.stderr.strip():
                ui.muted(f"Hook stderr: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        ui.warn("Hook timed out after 60s.")
    except Exception as e:
        ui.err(f"Hook error: {e}")
