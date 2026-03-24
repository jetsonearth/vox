"""Load/save ~/.vox/config.yaml and path resolution helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".vox"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULTS: dict[str, Any] = {
    "user_name": "Jetson",
    "vault_path": str(Path.home() / "My Vault"),
    "audio_archive": str(Path.home() / "Voice" / "archive"),
    "soniox_api_key": "",
    "force_tls12": True,
    "no_proxy": True,
    "language_hints": ["en", "zh"],
    "post_process_hook": "",
}


def load_config() -> dict[str, Any]:
    """Load config from ~/.vox/config.yaml, merged with defaults."""
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        cfg.update(user_cfg)
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """Write config to ~/.vox/config.yaml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)


def vault_path(cfg: dict[str, Any]) -> Path:
    return Path(cfg["vault_path"])


def audio_archive(cfg: dict[str, Any]) -> Path:
    return Path(cfg["audio_archive"])


def conversations_dir(cfg: dict[str, Any]) -> Path:
    return vault_path(cfg) / "Conversations"


def transcripts_dir(cfg: dict[str, Any]) -> Path:
    return vault_path(cfg) / "Conversations" / "Transcripts"


def calendar_dir(cfg: dict[str, Any]) -> Path:
    return vault_path(cfg) / "Calendar"


def templates_dir(cfg: dict[str, Any]) -> Path:
    return vault_path(cfg) / "Templates"


def prm_relationships_dir(cfg: dict[str, Any]) -> Path:
    return vault_path(cfg) / "PRM" / "Relationships"


def ensure_dirs(cfg: dict[str, Any]) -> None:
    """Create all required directories if they don't exist."""
    for d in [
        audio_archive(cfg),
        conversations_dir(cfg),
        transcripts_dir(cfg),
        calendar_dir(cfg),
    ]:
        d.mkdir(parents=True, exist_ok=True)
