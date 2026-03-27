# Vox Testing Instructions

Test the vox CLI tool at `/Users/ZhaobangJetWu/studio-kensense/vox/`. The vox binary is at `.venv/bin/vox` (also symlinked to `/opt/homebrew/bin/vox`).

## Prerequisites

Before testing, run `vox init` to create `~/.vox/config.yaml`. You'll need a Soniox API key for transcription tests. If you don't have one, skip the transcription/process tests and focus on unit tests.

## 1. Unit Tests (no API key needed)

Write and run these as pytest tests in `tests/`. Create the directory and files as needed. Install pytest first: `.venv/bin/pip install pytest`.

### 1a. `tests/test_naming.py`

Test `vox.naming`:
```python
from datetime import date
from vox.naming import make_slug, make_daily_note_filename, make_audio_filename, make_transcript_filename, make_note_title, make_archive_subdir

# make_slug
assert make_slug("RoboX Sync") == "robox-sync"
assert make_slug("Terry Chen") == "terry-chen"
assert make_slug("产品想法") == "产品想法"
assert make_slug("  hello   world  ") == "hello-world"
assert make_slug("德国🇩🇪Zillou") == "德国zillou"  # emoji stripped
assert make_slug("Phanos H. @ 2050 Materials") == "phanos-h-2050-materials"

# make_daily_note_filename
assert make_daily_note_filename(date(2026, 3, 23)) == "2026-03-23.md"
assert make_daily_note_filename(date(2025, 10, 5)) == "2025-10-05.md"

# make_audio_filename
assert make_audio_filename(date(2026, 3, 23), "terry-chen") == "2026-03-23-terry-chen.m4a"

# make_transcript_filename
assert make_transcript_filename(date(2026, 3, 23), "terry-chen") == "2026-03-23-terry-chen.md"
# Vault transcripts from vox are .txt (see make_transcript_txt_filename)

# make_note_title
assert make_note_title(date(2026, 3, 23), "Terry Chen") == "2026-03-23 Terry Chen"

# make_archive_subdir
assert make_archive_subdir(date(2026, 3, 23)) == "2026/03"
assert make_archive_subdir(date(2025, 1, 5)) == "2025/01"
```

### 1b. `tests/test_config.py`

Test `vox.config`:
```python
import tempfile
from pathlib import Path
from vox.config import load_config, save_config, DEFAULTS, vault_path, audio_archive, conversations_dir, transcripts_dir, calendar_dir

# Test defaults load when no config file exists
cfg = load_config()  # may load existing ~/.vox/config.yaml
assert "user_name" in cfg
assert "vault_path" in cfg
assert "soniox_api_key" in cfg

# Test path helpers
assert conversations_dir(cfg) == Path(cfg["vault_path"]) / "Conversations"
assert transcripts_dir(cfg) == Path(cfg["vault_path"]) / "Conversations" / "Transcripts"
assert calendar_dir(cfg) == Path(cfg["vault_path"]) / "Calendar"

# Test save/load round-trip with temp dir
import os
import vox.config as c
original_file = c.CONFIG_FILE
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        c.CONFIG_DIR = Path(tmpdir)
        c.CONFIG_FILE = Path(tmpdir) / "config.yaml"
        test_cfg = {"user_name": "TestUser", "vault_path": "/tmp/vault", "soniox_api_key": "test-key"}
        save_config(test_cfg)
        loaded = load_config()
        assert loaded["user_name"] == "TestUser"
        assert loaded["soniox_api_key"] == "test-key"
finally:
    c.CONFIG_FILE = original_file
```

### 1c. `tests/test_speaker.py`

Test `vox.speaker`:
```python
from vox.speaker import extract_speakers, get_preview, replace_speakers_auto

transcript = """Speaker 0:
[en] Hello, how are you doing today?

Speaker 1:
[zh] 我很好，谢谢你。
[en] Let's talk about the project.

Speaker 0:
[en] Sure, I have some updates."""

# extract_speakers
speakers = extract_speakers(transcript)
assert speakers == ["Speaker 0", "Speaker 1"]

# get_preview
preview = get_preview(transcript, "Speaker 0")
assert "Hello" in preview

preview1 = get_preview(transcript, "Speaker 1")
assert len(preview1) > 0

# replace_speakers_auto
result = replace_speakers_auto(transcript, ["Jetson", "Terry Chen"])
assert "Jetson:" in result
assert "Terry Chen:" in result
assert "Speaker 0:" not in result
assert "Speaker 1:" not in result

# Empty transcript
assert extract_speakers("No speakers here") == []
assert replace_speakers_auto("No speakers here", ["Name"]) == "No speakers here"
```

### 1d. `tests/test_contacts.py`

Test `vox.contacts`:
```python
import tempfile
from pathlib import Path
from vox.contacts import scan_contacts, fuzzy_match

# Test scan_contacts with temp dir
with tempfile.TemporaryDirectory() as tmpdir:
    rel_dir = Path(tmpdir)
    (rel_dir / "Terry Chen.md").write_text("# Terry", encoding="utf-8")
    (rel_dir / "Robotics").mkdir()
    (rel_dir / "Robotics" / "Tuo Liu.md").write_text("# Tuo", encoding="utf-8")

    contacts = scan_contacts(rel_dir)
    assert "Terry Chen" in contacts
    assert "Tuo Liu" in contacts
    assert len(contacts) == 2

# Test fuzzy_match
contacts = {"Terry Chen": Path("a.md"), "Tuo Liu": Path("b.md"), "Huey Lin": Path("c.md")}
assert fuzzy_match("terry", contacts) == "Terry Chen"
assert fuzzy_match("tuo", contacts) == "Tuo Liu"
assert fuzzy_match("xyzabc", contacts) is None

# Test empty dir
assert scan_contacts(Path("/nonexistent/dir")) == {}
```

### 1e. `tests/test_obsidian.py`

Test `vox.obsidian`:
```python
import tempfile
from datetime import date
from pathlib import Path
from vox.obsidian import build_frontmatter, save_transcript, ensure_daily_note, append_to_conversations_section

# Test frontmatter
fm = build_frontmatter(date(2026, 3, 23), ["Terry Chen"], "Gridmind")
assert "date: 2026-03-23" in fm
assert "[[Terry Chen]]" in fm
assert "---" in fm

# Empty people
fm_solo = build_frontmatter(date(2026, 3, 23), [], "Brain dump")
assert "people:" not in fm_solo

# Test save_transcript
with tempfile.TemporaryDirectory() as tmpdir:
    cfg = {"vault_path": tmpdir}
    (Path(tmpdir) / "Conversations" / "Transcripts").mkdir(parents=True)
    filename = save_transcript(date(2026, 3, 23), "terry-chen", "Hello world transcript", cfg)
    assert filename == "2026-03-23-terry-chen.txt"
    saved = (Path(tmpdir) / "Conversations" / "Transcripts" / filename).read_text()
    assert saved == "Hello world transcript"

# Test ensure_daily_note creates from template
with tempfile.TemporaryDirectory() as tmpdir:
    cfg = {"vault_path": tmpdir}
    cal_dir = Path(tmpdir) / "Calendar"
    cal_dir.mkdir()
    tmpl_dir = Path(tmpdir) / "Templates"
    tmpl_dir.mkdir()
    (tmpl_dir / "Daily Note Template.md").write_text("## Log\n\n## Conversations\n")

    daily = ensure_daily_note(date(2026, 3, 23), cfg)
    assert daily.exists()
    assert daily.name == "2026-03-23.md"
    content = daily.read_text()
    assert "## Conversations" in content

# Test ensure_daily_note finds suffixed file
with tempfile.TemporaryDirectory() as tmpdir:
    cfg = {"vault_path": tmpdir}
    cal_dir = Path(tmpdir) / "Calendar"
    cal_dir.mkdir()
    suffixed = cal_dir / "2026-03-09 (Terry Chat).md"
    suffixed.write_text("existing note")

    daily = ensure_daily_note(date(2026, 3, 9), cfg)
    assert daily == suffixed  # should find existing, not create new

# Test append_to_conversations_section
with tempfile.TemporaryDirectory() as tmpdir:
    daily = Path(tmpdir) / "test.md"
    daily.write_text("## Log\n\n## Conversations\n\n## Tomorrow\n")

    append_to_conversations_section(daily, "2026-03-23 Terry Chen")
    content = daily.read_text()
    assert "[[2026-03-23 Terry Chen]]" in content

    # Idempotent — second call should not duplicate
    append_to_conversations_section(daily, "2026-03-23 Terry Chen")
    assert content.count("[[2026-03-23 Terry Chen]]") == 1
```

### 1f. `tests/test_cli_date.py`

Test the date inference logic in `vox.cli`:
```python
import tempfile
from datetime import date
from pathlib import Path
from vox.cli import _infer_date

# Explicit --date override (ISO)
assert _infer_date(Path("anything.m4a"), "2026-03-21") == date(2026, 3, 21)

# Explicit --date override (M-D-YY)
assert _infer_date(Path("anything.m4a"), "3-21-26") == date(2026, 3, 21)

# Date from filename (YYYY-MM-DD)
assert _infer_date(Path("2026-03-21-terry.m4a"), None) == date(2026, 3, 21)

# Date from filename (M-D-YY)
assert _infer_date(Path("terry-3-21-26.m4a"), None) == date(2026, 3, 21)

# Falls back to file creation time when no date in filename
with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
    tmp = Path(f.name)
    result = _infer_date(tmp, None)
    assert result == date.today()  # just-created file
    tmp.unlink()
```

### 1g. `tests/test_transcriber.py`

Test `vox.transcriber.render_tokens` (no API call needed):
```python
from vox.transcriber import render_tokens

tokens = [
    {"text": "Hello ", "speaker": 0, "language": "en"},
    {"text": "how are you?", "speaker": 0, "language": "en"},
    {"text": "我很好", "speaker": 1, "language": "zh"},
    {"text": " thank you.", "speaker": 1, "language": "en"},
]

result = render_tokens(tokens)
assert "Speaker 0:" in result
assert "Speaker 1:" in result
assert "[en]" in result
assert "[zh]" in result
assert "Hello " in result
assert "我很好" in result
```

## 2. Integration Tests (need real files, no API)

### 2a. Test `vox init` dry run

```bash
# Check it doesn't crash — will prompt for input, you can Ctrl+C after verifying prompts appear
.venv/bin/vox init
```

### 2b. Test CLI help

```bash
.venv/bin/vox --help
.venv/bin/vox record --help
.venv/bin/vox process --help
```

All three should print usage without errors.

### 2c. Test process with missing file

```bash
.venv/bin/vox process /nonexistent/file.m4a --speaker terry
# Should print "Error: file not found" and exit 1
```

## 3. End-to-End Test (needs Soniox API key)

Only run this if `~/.vox/config.yaml` has a valid `soniox_api_key`.

Find a real `.m4a` file and run:

```bash
.venv/bin/vox process ~/path/to/real-recording.m4a --speaker terry --date 2026-03-22
```

Verify:
- [ ] Audio **moved** to `~/Voice/archive/2026/03/2026-03-22-terry-chen.m4a` (no duplicate in original folder)
- [ ] Transcript `.txt` saved right after transcription: `~/My Vault/Conversations/Transcripts/2026-03-22-terry-chen.txt`
- [ ] By default: no `Map speakers to names?` prompt; with `--name-speakers`, prompts appear as before
- [ ] Conversation note created at `~/My Vault/Conversations/2026-03-22 Terry Chen.md`
- [ ] Note has correct frontmatter (`date`, `people: [[Terry Chen]]`, `tags`)
- [ ] Note has `[[Transcripts/2026-03-22-terry-chen.txt]]` embed
- [ ] Daily note `~/My Vault/Calendar/2026-03-22.md` exists and has `[[2026-03-22 Terry Chen]]` link
- [ ] If codex is available: `# Analysis` section is populated
- [ ] If codex is not available: `# Analysis` has placeholder text

## Running All Unit Tests

```bash
cd /Users/ZhaobangJetWu/studio-kensense/vox
.venv/bin/pip install pytest
.venv/bin/pytest tests/ -v
```

All unit tests (1a–1g) should pass without any API keys, network access, or user interaction.
