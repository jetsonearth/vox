"""sox wrapper for audio recording."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path


def check_sox() -> bool:
    """Return True if sox is available."""
    return shutil.which("sox") is not None


def check_ffmpeg() -> bool:
    """Return True if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


def record(output_path: str | Path | None = None) -> Path:
    """Record audio via sox. Press Enter or Ctrl+C to stop.

    Returns the path to the recorded audio file (WAV, or M4A if ffmpeg available).
    """
    if not check_sox():
        raise RuntimeError("sox is not installed. Install with: brew install sox")

    # Record to a temp WAV first
    tmp_wav = tempfile.mktemp(suffix=".wav")

    cmd = ["sox", "-d", "-r", "44100", "-c", "1", tmp_wav]
    print("Recording... (press Enter to stop)")

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    try:
        # Wait for Enter key in a thread-safe way
        input()
    except (EOFError, KeyboardInterrupt):
        pass

    # Stop sox gracefully
    proc.send_signal(signal.SIGINT)
    proc.wait(timeout=5)

    # Check that we actually got audio
    wav_path = Path(tmp_wav)
    if not wav_path.exists() or wav_path.stat().st_size < 1000:
        wav_path.unlink(missing_ok=True)
        raise RuntimeError("Recording failed — no audio captured. Check your microphone.")

    # Convert to M4A if ffmpeg is available
    if check_ffmpeg():
        if output_path:
            m4a_path = Path(output_path)
        else:
            m4a_path = Path(tempfile.mktemp(suffix=".m4a"))

        m4a_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["ffmpeg", "-i", tmp_wav, "-c:a", "aac", "-b:a", "128k", "-y", str(m4a_path)],
                capture_output=True, check=True,
            )
            wav_path.unlink()
            print(f"Recorded: {m4a_path}")
            return m4a_path
        except subprocess.CalledProcessError:
            # Fall back to WAV
            print("ffmpeg conversion failed, keeping WAV.")

    if output_path:
        final = Path(output_path).with_suffix(".wav")
        final.parent.mkdir(parents=True, exist_ok=True)
        wav_path.rename(final)
        print(f"Recorded: {final}")
        return final

    print(f"Recorded: {wav_path}")
    return wav_path
