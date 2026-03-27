"""codex exec wrapper for transcript analysis."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from . import ui

PROMPT_FILE = Path(__file__).parent / "default_analysis_prompt.txt"
_VOX_PROJECT_DIR = Path(__file__).parent.parent  # vox repo root — trusted in codex
TIMEOUT_SEC = 900  # 15 minutes — long transcripts need more time

_ATX_HEADING = re.compile(r"^(#{1,6})(\s+)(.*)$")


def _demote_analysis_headings(text: str) -> str:
    """Add one level to each ATX heading so analysis nests under the note's ``# Analysis``."""
    out_lines: list[str] = []
    for line in text.splitlines():
        m = _ATX_HEADING.match(line)
        if not m:
            out_lines.append(line)
            continue
        depth = len(m.group(1))
        new_depth = min(depth + 1, 6)
        out_lines.append(f"{'#' * new_depth}{m.group(2)}{m.group(3)}")
    return "\n".join(out_lines)


def analyze(transcript: str, prompt_path: str | Path | None = None) -> str | None:
    """Run analysis via codex. Returns analysis text or None on failure."""
    if not _check_codex():
        ui.muted("codex not on PATH — skipping analysis.")
        return None

    prompt_file = Path(prompt_path) if prompt_path else PROMPT_FILE
    if not prompt_file.exists():
        ui.warn(f"Analysis prompt not found: {prompt_file} — skipping.")
        return None

    prompt_text = prompt_file.read_text(encoding="utf-8")
    full_input = f"{prompt_text}\n\n---\n\nTRANSCRIPT:\n\n{transcript}"

    # Write to temp file for codex input
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(full_input)
        tmp_path = tmp.name

    try:
        with ui.spinner("Running codex analysis (can take several minutes)…"):
            # Try passing as prompt string first, fall back to file path
            result = subprocess.run(
                [
                    "codex", "exec",
                    "-m", "gpt-5.4",
                    "--skip-git-repo-check",
                    tmp_path,
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEC,
                cwd=str(_VOX_PROJECT_DIR),
            )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            ui.err(f"codex exit {result.returncode}:")
            for line in stderr.splitlines()[:30]:
                ui.muted(f"  {line}")
            if stdout:
                ui.err("codex stdout:")
                for line in stdout.splitlines()[:10]:
                    ui.muted(f"  {line}")
            return None
        ui.ok("Analysis finished")
        return _demote_analysis_headings(result.stdout.strip())
    except FileNotFoundError:
        ui.muted("codex not found — skipping analysis.")
        return None
    except subprocess.TimeoutExpired:
        ui.warn(f"codex timed out after {TIMEOUT_SEC // 60} minutes — skipping analysis.")
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _check_codex() -> bool:
    """Return True if codex is available on PATH."""
    import shutil
    return shutil.which("codex") is not None
