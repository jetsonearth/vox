"""Transcript analysis via Claude Code CLI (preferred) or codex exec (fallback)."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import ui

PROMPT_FILE = Path(__file__).parent / "default_analysis_prompt.txt"
_VOX_PROJECT_DIR = Path(__file__).parent.parent
TIMEOUT_SEC = 900

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
    """Run analysis. Tries Claude Code first, falls back to codex exec."""
    result = _analyze_claude_code(transcript, prompt_path)
    if result is not None:
        return result

    return _analyze_codex(transcript, prompt_path)


# ---------------------------------------------------------------------------
# Claude Code CLI
# ---------------------------------------------------------------------------

_CLAUDE_PATH: str | None = None


def _find_claude() -> str | None:
    global _CLAUDE_PATH
    if _CLAUDE_PATH is not None:
        return _CLAUDE_PATH

    # Check common locations
    for path in [
        shutil.which("claude"),
        "/opt/homebrew/bin/claude",
        "/usr/local/bin/claude",
    ]:
        if path and Path(path).exists():
            _CLAUDE_PATH = path
            return path
    return None


def _analyze_claude_code(
    transcript: str,
    prompt_path: str | Path | None = None,
) -> str | None:
    """Analyze transcript using Claude Code CLI."""
    claude = _find_claude()
    if not claude:
        ui.muted("claude not on PATH - trying codex instead.")
        return None

    prompt_file = Path(prompt_path) if prompt_path else PROMPT_FILE
    if not prompt_file.exists():
        ui.warn(f"Analysis prompt not found: {prompt_file}")
        return None

    prompt_text = prompt_file.read_text(encoding="utf-8")
    full_input = f"{prompt_text}\n\n---\n\nTRANSCRIPT:\n\n{transcript}"

    # Write to temp file and pipe to claude
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(full_input)
        tmp_path = tmp.name

    try:
        with ui.timed_spinner("Running Claude analysis...") as elapsed:
            result = subprocess.run(
                [
                    claude,
                    "-p", full_input,
                    "--output-format", "text",
                    "--model", "opus",
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEC,
            )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            ui.warn(f"Claude exit {result.returncode}")
            if stderr:
                for line in stderr.splitlines()[:10]:
                    ui.muted(f"  {line}")
            return None

        output = result.stdout.strip()
        if not output:
            ui.warn("Claude returned empty output")
            return None

        ui.ok("Claude analysis finished", elapsed())
        return _demote_analysis_headings(output)
    except subprocess.TimeoutExpired:
        ui.warn(f"Claude timed out after {TIMEOUT_SEC // 60} minutes")
        return None
    except Exception as e:
        ui.warn(f"Claude error: {e}")
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Codex exec (fallback)
# ---------------------------------------------------------------------------


def _analyze_codex(
    transcript: str,
    prompt_path: str | Path | None = None,
) -> str | None:
    """Run analysis via codex exec."""
    if not shutil.which("codex"):
        ui.muted("codex not on PATH - skipping analysis.")
        return None

    prompt_file = Path(prompt_path) if prompt_path else PROMPT_FILE
    if not prompt_file.exists():
        ui.warn(f"Analysis prompt not found: {prompt_file} - skipping.")
        return None

    prompt_text = prompt_file.read_text(encoding="utf-8")
    full_input = f"{prompt_text}\n\n---\n\nTRANSCRIPT:\n\n{transcript}"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(full_input)
        tmp_path = tmp.name

    try:
        with ui.spinner("Running codex analysis (can take several minutes)..."):
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
        ui.muted("codex not found - skipping analysis.")
        return None
    except subprocess.TimeoutExpired:
        ui.warn(f"codex timed out after {TIMEOUT_SEC // 60} minutes - skipping analysis.")
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Speaker identification (unused in current flow but kept for future use)
# ---------------------------------------------------------------------------


def identify_speakers(
    transcript: str,
    participant_names: list[str],
    user_name: str = "Jetson",
) -> dict[str, str] | None:
    """Use Claude or codex to map Speaker N labels to real names based on context."""
    from .speaker import extract_speakers
    import json

    speakers = extract_speakers(transcript)
    if not speakers:
        return None

    all_names = [user_name] + participant_names

    prompt = f"""You are given a diarized conversation transcript where speakers are labeled {', '.join(speakers)}.

The participants in this conversation are: {', '.join(all_names)}.
{user_name} is the person who recorded this conversation.

Determine which speaker label corresponds to which real person.
Return ONLY a valid JSON object. No explanation, no markdown.

Example: {{"Speaker 2": "Jetson", "Speaker 3": "Alex"}}

---

TRANSCRIPT (first 3000 chars):

{transcript[:3000]}
"""

    # Try claude first
    claude = _find_claude()
    if claude:
        try:
            with ui.spinner("Identifying speakers via Claude..."):
                result = subprocess.run(
                    [claude, "-p", prompt, "--output-format", "text"],
                    capture_output=True, text=True, timeout=120,
                )
            if result.returncode == 0:
                raw = result.stdout.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                mapping = json.loads(raw)
                if isinstance(mapping, dict):
                    valid = {k: v for k, v in mapping.items() if k in speakers and v in all_names}
                    if valid:
                        ui.ok(f"Speaker mapping: {valid}")
                        return valid
        except Exception:
            pass

    # Fallback to codex
    if shutil.which("codex"):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(prompt)
            tmp_path = tmp.name
        try:
            with ui.spinner("Identifying speakers via codex..."):
                result = subprocess.run(
                    ["codex", "exec", "-m", "gpt-5.4", "--skip-git-repo-check", tmp_path],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(_VOX_PROJECT_DIR),
                )
            if result.returncode == 0:
                raw = result.stdout.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                mapping = json.loads(raw)
                if isinstance(mapping, dict):
                    valid = {k: v for k, v in mapping.items() if k in speakers and v in all_names}
                    if valid:
                        ui.ok(f"Speaker mapping: {valid}")
                        return valid
        except Exception:
            pass
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return None
