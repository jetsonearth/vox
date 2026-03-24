"""Tests for vox.config."""

import tempfile
from pathlib import Path

import vox.config as c
from vox.config import (
    audio_archive,
    calendar_dir,
    conversations_dir,
    load_config,
    save_config,
    transcripts_dir,
    vault_path,
)


def test_load_config_has_expected_keys():
    cfg = load_config()
    assert "user_name" in cfg
    assert "vault_path" in cfg
    assert "soniox_api_key" in cfg


def test_path_helpers():
    cfg = load_config()
    assert conversations_dir(cfg) == Path(cfg["vault_path"]) / "Conversations"
    assert transcripts_dir(cfg) == Path(cfg["vault_path"]) / "Conversations" / "Transcripts"
    assert calendar_dir(cfg) == Path(cfg["vault_path"]) / "Calendar"
    assert isinstance(vault_path(cfg), Path)
    assert isinstance(audio_archive(cfg), Path)


def test_save_load_roundtrip():
    original_file = c.CONFIG_FILE
    original_dir = c.CONFIG_DIR
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            c.CONFIG_DIR = Path(tmpdir)
            c.CONFIG_FILE = Path(tmpdir) / "config.yaml"
            test_cfg = {
                "user_name": "TestUser",
                "vault_path": "/tmp/vault",
                "soniox_api_key": "test-key",
            }
            save_config(test_cfg)
            loaded = load_config()
            assert loaded["user_name"] == "TestUser"
            assert loaded["soniox_api_key"] == "test-key"
    finally:
        c.CONFIG_FILE = original_file
        c.CONFIG_DIR = original_dir
