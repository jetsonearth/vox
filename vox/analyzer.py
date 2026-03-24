"""codex exec wrapper for transcript analysis."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

PROMPT_FILE = Path(__file__).parent.parent / "default_analysis_prompt.txt"
TIMEOUT_SEC = 300  # 5 minutes


def analyze(transcript: str, prompt_path: str | Path | None = None) -> str | None:
    """Run analysis via codex. Returns analysis text or None on failure."""
    if not _check_codex():
        print("  codex not found — skipping analysis.")
        return None

    prompt_file = Path(prompt_path) if prompt_path else PROMPT_FILE
    if not prompt_file.exists():
        print(f"  Analysis prompt not found: {prompt_file} — skipping.")
        return None

    prompt_text = prompt_file.read_text(encoding="utf-8")
    full_input = f"{prompt_text}\n\n---\n\nTRANSCRIPT:\n\n{transcript}"

    # Write to temp file for codex input
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(full_input)
        tmp_path = tmp.name

    try:
        print("  Running analysis via codex...")
        result = subprocess.run(
            ["codex", "exec", tmp_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            print(f"  codex returned exit code {result.returncode}: {stderr[:200]}")
            return None
        return result.stdout.strip()
    except FileNotFoundError:
        print("  codex not found — skipping analysis.")
        return None
    except subprocess.TimeoutExpired:
        print("  codex timed out after 5 minutes — skipping analysis.")
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _check_codex() -> bool:
    """Return True if codex is available on PATH."""
    import shutil
    return shutil.which("codex") is not None
