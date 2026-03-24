"""Soniox API transcription — adapted from RoboX soniox.py."""

from __future__ import annotations

import ssl
import time
from pathlib import Path
from typing import Any, Optional

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, HTTPError, SSLError, Timeout
from urllib3.util.retry import Retry

SONIOX_API_BASE_URL = "https://api.soniox.com"
DEFAULT_TIMEOUT_SEC = 120.0
DEFAULT_NETWORK_RETRIES = 4
DEFAULT_RETRY_BACKOFF_SEC = 1.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


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


def _api_request(session: Session, method: str, path: str, timeout_sec: float, **kwargs) -> requests.Response:
    return session.request(method=method, url=f"{SONIOX_API_BASE_URL}{path}", timeout=timeout_sec, **kwargs)


def _parse_json(res: requests.Response, action: str) -> dict:
    try:
        return res.json()
    except ValueError as exc:
        preview = (res.text or "").strip().replace("\n", " ")[:300]
        raise RuntimeError(f"Failed to {action}: non-JSON response (HTTP {res.status_code}): {preview}") from exc


def _upload_audio(session: Session, audio_path: str, timeout_sec: float, network_retries: int, retry_backoff_sec: float) -> str:
    print("Uploading audio...")
    max_attempts = max(1, network_retries + 1)
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            with open(audio_path, "rb") as audio_file:
                res = _api_request(session, "POST", "/v1/files", timeout_sec, files={"file": (Path(audio_path).name, audio_file)})

            if res.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
                sleep_sec = retry_backoff_sec * (2 ** (attempt - 1))
                print(f"  Upload attempt {attempt}/{max_attempts} → HTTP {res.status_code}, retrying in {sleep_sec:.1f}s...")
                time.sleep(sleep_sec)
                continue

            res.raise_for_status()
            file_id = _parse_json(res, "upload audio").get("id")
            if not file_id:
                raise RuntimeError("Upload succeeded but response missing file id.")
            print(f"  File ID: {file_id}")
            return file_id
        except (SSLError, ConnectionError, Timeout) as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            sleep_sec = retry_backoff_sec * (2 ** (attempt - 1))
            print(f"  Upload attempt {attempt}/{max_attempts} failed ({type(exc).__name__}), retrying in {sleep_sec:.1f}s...")
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


def transcribe(audio_path: str, cfg: dict[str, Any]) -> str:
    """Transcribe a local audio file via Soniox. Returns transcript text."""
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

    stt_config: dict[str, Any] = {
        "model": "stt-async-v4",
        "language_hints": cfg.get("language_hints", ["en", "zh"]),
        "enable_language_identification": True,
        "enable_speaker_diarization": True,
        "file_id": file_id,
    }

    transcription_id: Optional[str] = None
    try:
        # Create transcription
        print("Creating transcription...")
        res = _api_request(session, "POST", "/v1/transcriptions", timeout, json=stt_config)
        res.raise_for_status()
        transcription_id = _parse_json(res, "create transcription").get("id")
        if not transcription_id:
            raise RuntimeError("Create transcription response missing id.")
        print(f"  Transcription ID: {transcription_id}")

        # Poll until complete
        print("Waiting for transcription...")
        while True:
            res = _api_request(session, "GET", f"/v1/transcriptions/{transcription_id}", timeout)
            res.raise_for_status()
            data = _parse_json(res, "check status")
            if data["status"] == "completed":
                break
            elif data["status"] == "error":
                raise RuntimeError(f"Transcription error: {data.get('error_message', 'Unknown')}")
            time.sleep(1)

        # Fetch result
        res = _api_request(session, "GET", f"/v1/transcriptions/{transcription_id}/transcript", timeout)
        res.raise_for_status()
        result = _parse_json(res, "fetch transcript")

    finally:
        # Cleanup remote resources
        if transcription_id:
            try:
                _api_request(session, "DELETE", f"/v1/transcriptions/{transcription_id}", timeout)
            except Exception as e:
                print(f"  Warning: failed to delete transcription: {e}")
        try:
            _api_request(session, "DELETE", f"/v1/files/{file_id}", timeout)
        except Exception as e:
            print(f"  Warning: failed to delete uploaded file: {e}")

    transcript = render_tokens(result["tokens"])
    print("Transcription complete.")
    return transcript
