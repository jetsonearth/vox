"""sox wrapper for audio recording."""

from __future__ import annotations

import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from . import ui


def check_sox() -> bool:
    """Return True if sox is available."""
    return shutil.which("sox") is not None


def check_ffmpeg() -> bool:
    """Return True if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


# ---------------------------------------------------------------------------
# Non-blocking recording API (for server / GUI use)
# ---------------------------------------------------------------------------


class RecordingSession:
    """Manages a single sox recording session without blocking."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._tmp_wav: str = ""
        self._started_at: float = 0.0
        self._stopped_at: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def elapsed(self) -> float:
        if self._started_at == 0:
            return 0.0
        end = self._stopped_at if self._stopped_at else time.monotonic()
        return end - self._started_at

    def start(self) -> None:
        """Start recording. Raises if already recording or sox missing."""
        if self.is_recording:
            raise RuntimeError("Already recording")
        if not check_sox():
            raise RuntimeError("sox is not installed. Install with: brew install sox")

        self._tmp_wav = tempfile.mktemp(suffix=".wav")
        self._stopped_at = 0.0
        cmd = ["sox", "-d", "-r", "44100", "-c", "1", self._tmp_wav]
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        self._started_at = time.monotonic()

    def stop(self) -> Path:
        """Stop recording and return the WAV path. Raises if not recording."""
        if not self.is_recording:
            raise RuntimeError("Not recording")
        self._stopped_at = time.monotonic()
        self._proc.send_signal(signal.SIGINT)
        self._proc.wait(timeout=5)
        self._proc = None

        wav_path = Path(self._tmp_wav)
        if not wav_path.exists() or wav_path.stat().st_size < 1000:
            wav_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Recording failed - no audio captured. Check your microphone."
            )
        return wav_path

    def abort(self) -> None:
        """Kill the recording and discard the audio."""
        if self._proc and self._proc.poll() is None:
            self._proc.send_signal(signal.SIGINT)
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        if self._tmp_wav:
            Path(self._tmp_wav).unlink(missing_ok=True)
        self._started_at = 0.0
        self._stopped_at = 0.0


def convert_to_m4a(wav_path: Path, output_path: Path | None = None) -> Path:
    """Convert a WAV file to M4A using ffmpeg. Returns the M4A path.

    Falls back to returning the original WAV if ffmpeg is unavailable or fails.
    """
    if not check_ffmpeg():
        return wav_path

    m4a_path = output_path or Path(tempfile.mktemp(suffix=".m4a"))
    m4a_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                "ffmpeg", "-i", str(wav_path),
                "-c:a", "aac", "-b:a", "128k", "-y",
                str(m4a_path),
            ],
            capture_output=True,
            check=True,
        )
        wav_path.unlink()
        return m4a_path
    except subprocess.CalledProcessError:
        return wav_path


# ---------------------------------------------------------------------------
# Original blocking API (CLI backward compat)
# ---------------------------------------------------------------------------


def record(output_path: str | Path | None = None) -> Path:
    """Record audio via sox. Press Enter or Ctrl+C to stop.

    Returns the path to the recorded audio file (WAV, or M4A if ffmpeg available).
    """
    session = RecordingSession()
    session.start()
    ui.recording_hint()

    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass

    wav_path = session.stop()

    # Convert to M4A
    if output_path:
        dest = Path(output_path)
    else:
        dest = None

    if check_ffmpeg():
        with ui.spinner("Converting to M4A..."):
            final = convert_to_m4a(wav_path, dest)
        ui.ok(f"Recorded {final}")
        return final

    if dest:
        final = dest.with_suffix(".wav")
        final.parent.mkdir(parents=True, exist_ok=True)
        wav_path.rename(final)
        ui.ok(f"Recorded {final}")
        return final

    ui.ok(f"Recorded {wav_path}")
    return wav_path
