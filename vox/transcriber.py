"""Soniox API transcription — adapted from RoboX soniox.py."""

from __future__ import annotations

import ssl
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests

from . import ui
from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, HTTPError, SSLError, Timeout
from urllib3.util.retry import Retry

SONIOX_API_BASE_URL = "https://api.soniox.com"
DEFAULT_TIMEOUT_SEC = 120.0
DEFAULT_NETWORK_RETRIES = 4
DEFAULT_RETRY_BACKOFF_SEC = 1.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# (connect, read) read timeout must cover Soniox buffering a huge transcript JSON before first byte.
_TRANSCRIPT_READ_CAP_SEC = 14_400.0  # 4 hours
_TRANSCRIPT_READ_MIN_SEC = 300.0


@dataclass
class Token:
    """A single transcribed token with timing and metadata."""

    text: str
    start_ms: int = 0
    end_ms: int = 0
    speaker: int | None = None
    language: str | None = None

    @staticmethod
    def from_soniox(raw: dict) -> "Token":
        return Token(
            text=raw.get("text", ""),
            start_ms=raw.get("start_ms", 0),
            end_ms=raw.get("end_ms", 0),
            speaker=raw.get("speaker"),
            language=raw.get("language"),
        )


@dataclass
class TranscriptResult:
    """Structured transcript with tokens and rendered text."""

    text: str
    tokens: list[Token] = field(default_factory=list)
    raw_tokens: list[dict] = field(default_factory=list)

    def __str__(self) -> str:
        return self.text


def _transcript_read_timeout_sec(audio_duration_ms: int | None, cfg: dict[str, Any]) -> float:
    """Seconds to allow for ``GET …/transcript`` with no bytes (Soniox may buffer a large body)."""
    override = cfg.get("soniox_transcript_timeout_sec")
    if override is not None:
        return float(override)
    if not audio_duration_ms or audio_duration_ms <= 0:
        return 600.0
    audio_sec = audio_duration_ms / 1000.0
    return max(_TRANSCRIPT_READ_MIN_SEC, min(_TRANSCRIPT_READ_CAP_SEC, audio_sec * 4.0))


class TLS12HttpAdapter(HTTPAdapter):
    """Force TLS 1.2 for environments with TLS 1.3 handshake EOF issues."""

    def _tls12_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        return ctx

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["ssl_context"] = self._tls12_context()
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs["ssl_context"] = self._tls12_context()
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def build_session(
    api_key: str,
    network_retries: int = DEFAULT_NETWORK_RETRIES,
    retry_backoff_sec: float = DEFAULT_RETRY_BACKOFF_SEC,
    force_tls12: bool = True,
    no_proxy: bool = True,
) -> Session:
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {api_key}"

    if no_proxy:
        session.trust_env = False

    retry = Retry(
        total=network_retries,
        connect=network_retries,
        read=network_retries,
        status=network_retries,
        backoff_factor=retry_backoff_sec,
        status_forcelist=sorted(RETRYABLE_STATUS_CODES),
        allowed_methods=None,
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter_cls = TLS12HttpAdapter if force_tls12 else HTTPAdapter
    adapter = adapter_cls(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _api_request(
    session: Session,
    method: str,
    path: str,
    timeout: float | tuple[float, float],
    **kwargs,
) -> requests.Response:
    return session.request(method=method, url=f"{SONIOX_API_BASE_URL}{path}", timeout=timeout, **kwargs)


def _parse_json(res: requests.Response, action: str) -> dict:
    try:
        return res.json()
    except ValueError as exc:
        preview = (res.text or "").strip().replace("\n", " ")[:300]
        raise RuntimeError(f"Failed to {action}: non-JSON response (HTTP {res.status_code}): {preview}") from exc


def _upload_audio(session: Session, audio_path: str, timeout_sec: float, network_retries: int, retry_backoff_sec: float) -> str:
    max_attempts = max(1, network_retries + 1)
    last_error: Optional[Exception] = None

    with ui.timed_spinner("Uploading audio to Soniox…") as elapsed:
        for attempt in range(1, max_attempts + 1):
            try:
                with open(audio_path, "rb") as audio_file:
                    res = _api_request(session, "POST", "/v1/files", timeout_sec, files={"file": (Path(audio_path).name, audio_file)})

                if res.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
                    sleep_sec = retry_backoff_sec * (2 ** (attempt - 1))
                    ui.warn(f"Upload {attempt}/{max_attempts} → HTTP {res.status_code}, retry in {sleep_sec:.1f}s…")
                    time.sleep(sleep_sec)
                    continue

                res.raise_for_status()
                file_id = _parse_json(res, "upload audio").get("id")
                if not file_id:
                    raise RuntimeError("Upload succeeded but response missing file id.")
                ui.ok("Audio uploaded", elapsed())
                ui.label_value("File ID", file_id)
                return file_id
            except (SSLError, ConnectionError, Timeout) as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                sleep_sec = retry_backoff_sec * (2 ** (attempt - 1))
                ui.warn(f"Upload {attempt}/{max_attempts} failed ({type(exc).__name__}), retry in {sleep_sec:.1f}s…")
                time.sleep(sleep_sec)
            except HTTPError as exc:
                response = exc.response
                status = response.status_code if response is not None else "unknown"
                body = (response.text or "")[:300] if response is not None else ""
                raise RuntimeError(f"Failed to upload audio (HTTP {status}): {body}") from exc

    raise RuntimeError("Upload failed after retries. Try --force_tls12 / --no_proxy.") from last_error


def render_tokens(tokens: list[dict]) -> str:
    """Convert Soniox tokens into a readable transcript."""
    parts: list[str] = []
    current_speaker: Optional[str] = None
    current_language: Optional[str] = None

    for token in tokens:
        text = token["text"]
        speaker = token.get("speaker")
        language = token.get("language")

        if speaker is not None and speaker != current_speaker:
            if current_speaker is not None:
                parts.append("\n\n")
            current_speaker = speaker
            current_language = None
            parts.append(f"Speaker {current_speaker}:")

        if language is not None and language != current_language:
            current_language = language
            parts.append(f"\n[{current_language}] ")
            text = text.lstrip()

        parts.append(text)

    return "".join(parts)


def transcribe(
    audio_path: str,
    cfg: dict[str, Any],
    *,
    language_hints: list[str] | None = None,
    context: str | None = None,
    enable_soniox_diarization: bool | None = None,
) -> TranscriptResult:
    """Transcribe a local audio file via Soniox. Returns ``TranscriptResult``.

    ``language_hints`` — ISO codes Soniox should expect (see API ``language_hints``).
    ``context`` — optional string or domain notes (Soniox ``context`` field) for
    better vocabulary and formatting.
    ``enable_soniox_diarization`` — if ``None``, defaults to ``not cfg.get("enable_diarization")``.
    When pyannote diarization is enabled, Soniox diarization is turned off.
    """
    api_key = cfg.get("soniox_api_key") or ""
    if not api_key:
        raise RuntimeError("Missing soniox_api_key in config. Run `vox init` first.")

    session = build_session(
        api_key=api_key,
        force_tls12=cfg.get("force_tls12", True),
        no_proxy=cfg.get("no_proxy", True),
    )

    timeout = DEFAULT_TIMEOUT_SEC
    retries = DEFAULT_NETWORK_RETRIES
    backoff = DEFAULT_RETRY_BACKOFF_SEC

    file_id = _upload_audio(session, audio_path, timeout, retries, backoff)

    hints = (
        language_hints
        if language_hints is not None
        else list(cfg.get("language_hints", ["en", "zh"]))
    )

    # Determine whether Soniox should do its own diarization.
    # When pyannote diarization is active, we turn Soniox diarization off.
    if enable_soniox_diarization is None:
        use_soniox_diar = not cfg.get("enable_diarization", False)
    else:
        use_soniox_diar = enable_soniox_diarization

    stt_config: dict[str, Any] = {
        "model": "stt-async-v4",
        "language_hints": hints,
        "enable_language_identification": True,
        "enable_speaker_diarization": use_soniox_diar,
        "file_id": file_id,
    }
    if context:
        stt_config["context"] = context

    transcription_id: Optional[str] = None
    try:
        with ui.spinner("Creating transcription job…"):
            res = _api_request(session, "POST", "/v1/transcriptions", timeout, json=stt_config)
            res.raise_for_status()
            transcription_id = _parse_json(res, "create transcription").get("id")
            if not transcription_id:
                raise RuntimeError("Create transcription response missing id.")
        ui.label_value("Transcription ID", transcription_id)

        audio_duration_ms: int | None = None
        poll_t0 = time.monotonic()
        with ui.soniox_poll_progress("Transcribing — Soniox is processing…") as set_status:
            while True:
                res = _api_request(session, "GET", f"/v1/transcriptions/{transcription_id}", timeout)
                res.raise_for_status()
                data = _parse_json(res, "check status")
                st = data["status"]
                set_status(f"Soniox: {st}")
                if st == "completed":
                    raw_dur = data.get("audio_duration_ms")
                    if raw_dur is not None:
                        try:
                            audio_duration_ms = int(raw_dur)
                        except (TypeError, ValueError):
                            audio_duration_ms = None
                    break
                elif st == "error":
                    raise RuntimeError(f"Transcription error: {data.get('error_message', 'Unknown')}")
                time.sleep(1)
        ui.ok("Soniox processing complete", time.monotonic() - poll_t0)

        read_timeout = _transcript_read_timeout_sec(audio_duration_ms, cfg)
        with ui.timed_spinner(f"Fetching transcript JSON (timeout {read_timeout / 60:.0f}m)…") as elapsed:
            res = _api_request(
                session,
                "GET",
                f"/v1/transcriptions/{transcription_id}/transcript",
                (60.0, read_timeout),
            )
            res.raise_for_status()
            result = _parse_json(res, "fetch transcript")
        ui.ok("Transcript fetched", elapsed())

    finally:
        if transcription_id:
            try:
                _api_request(session, "DELETE", f"/v1/transcriptions/{transcription_id}", timeout)
            except Exception as e:
                ui.warn(f"Could not delete remote transcription: {e}")
        try:
            _api_request(session, "DELETE", f"/v1/files/{file_id}", timeout)
        except Exception as e:
            ui.warn(f"Could not delete uploaded file: {e}")

    ui.muted("Formatting transcript…")
    raw_tokens = result["tokens"]
    transcript = render_tokens(raw_tokens)
    tokens = [Token.from_soniox(t) for t in raw_tokens]
    ui.ok("Transcription complete")
    return TranscriptResult(text=transcript, tokens=tokens, raw_tokens=raw_tokens)
