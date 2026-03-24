# Vox

Voice recording pipeline automation. One command to record, transcribe, analyze, and archive a conversation into Obsidian.

## What It Does

```
vox record terry → record → stop → confirm speakers → transcribe → analyze → archive
```

Every conversation produces **4 outputs**:

| # | Output | Location |
|---|--------|----------|
| 1 | Audio | `~/Voice/archive/2026/03/2026-03-23-terry-chen.m4a` |
| 2 | Transcript | `~/My Vault/Conversations/Transcripts/2026-03-23-terry-chen.md` |
| 3 | Conversation Note | `~/My Vault/Conversations/2026-03-23 Terry Chen.md` |
| 4 | Daily note link | `[[2026-03-23 Terry Chen]]` appended to `Calendar/2026-03-23.md` |

Plus an optional post-process hook (e.g. update Bondfyre people card).

---

## Install

```bash
# From the vox project directory
python3 -m venv .venv
.venv/bin/pip install -e .

# Symlink for global access
ln -sf $(pwd)/.venv/bin/vox /opt/homebrew/bin/vox
```

### Dependencies

| Tool | Required? | Install |
|------|-----------|---------|
| **sox** | Yes (for `vox record`) | `brew install sox` |
| **ffmpeg** | Recommended (WAV → M4A) | `brew install ffmpeg` |
| **codex** | Optional (analysis) | See OpenAI docs |
| **Soniox API key** | Yes (transcription) | [soniox.com](https://soniox.com) |

---

## Setup

```bash
vox init
```

Interactive wizard that:
1. Asks your name, vault path, Soniox API key
2. Checks that sox / ffmpeg / codex are installed
3. Creates `~/.vox/config.yaml`
4. Creates required directories (`~/Voice/archive/`, vault subdirs)

### Config File (`~/.vox/config.yaml`)

```yaml
user_name: Jetson
vault_path: /Users/you/My Vault
audio_archive: /Users/you/Voice/archive
soniox_api_key: your-key-here
force_tls12: true          # Fix for TLS 1.3 handshake issues
no_proxy: true             # Bypass HTTP_PROXY for Soniox calls
language_hints:            # Soniox language detection
  - en
  - zh
post_process_hook: ""      # Path to optional script (see Hooks below)
```

---

## Commands

### `vox record` — Record + full pipeline

```bash
# 1-on-1 conversation (most common)
vox record terry

# Multi-person meeting
vox record "RoboX Sync" --speakers terry,tuo,huey

# Solo brain dump (no people card, no PRM lookup)
vox record --solo "产品想法"
```

**What happens step by step:**

1. **Record** — sox captures audio from default mic. Press **Enter** or **Ctrl+C** to stop.
2. **Archive audio** — Saved directly to `~/Voice/archive/YYYY/MM/YYYY-MM-DD-slug.m4a`
3. **Transcribe** — Uploaded to Soniox API (async STT v4, bilingual en/zh, speaker diarization). Remote files cleaned up after.
4. **Speaker confirmation** — Shows first 2 sentences per speaker, suggests names from your input. You confirm or correct interactively.
5. **Save transcript** — Markdown file in `Conversations/Transcripts/YYYY-MM-DD-slug.md` (plain text inside)
6. **Analyze** — Pipes transcript + prompt through `codex exec`. Non-fatal if codex is missing.
7. **Create conversation note** — Markdown with frontmatter, transcript embed, analysis section.
8. **Link daily note** — Finds or creates `Calendar/YYYY-MM-DD.md`, appends `[[conversation]]` link.
9. **Run hook** — Optional post-process script with env vars.

### `vox process` — Process an existing audio file

For recordings you already have (e.g. from your phone, Downloads, another app):

```bash
# Basic — speaker name required
vox process ~/Downloads/meeting.m4a --speaker terry

# Multiple speakers
vox process ~/Downloads/sync.m4a --speaker terry,tuo,huey

# With topic override (used as the note title)
vox process ~/Downloads/call.m4a --speaker terry --topic "Gridmind Strategy"

# Explicit date override
vox process ~/Downloads/old-call.m4a --speaker terry --date 2026-03-21
```

**Date detection** (in priority order):
1. `--date` flag (supports `YYYY-MM-DD` or `M-D-YY`)
2. Date in filename (e.g. `terry-3-21-26.m4a` → 2026-03-21)
3. File creation time (`st_birthtime` on macOS)
4. Today's date (last resort)

The audio is **copied** (not moved) to the archive. Original stays in place.

### `vox init` — Setup wizard

```bash
vox init
```

See [Setup](#setup) above.

---

## Pipeline Detail

### Recording (`recorder.py`)

- Uses `sox -d -r 44100 -c 1` to record mono 44.1kHz WAV
- Converts to M4A via ffmpeg (128k AAC) if available
- Falls back to WAV if ffmpeg is missing or fails
- Checks file size > 1KB to catch dead-mic situations

### Transcription (`transcriber.py`)

Adapted from RoboX's `soniox.py`. Key features:
- **TLS 1.2 forced** by default (fixes `SSLEOF` handshake errors common in China)
- **Retry with backoff** — 4 retries, 1.5s exponential backoff on 429/5xx
- **Cleanup** — always deletes uploaded file and transcription from Soniox after fetching results (via try/finally)
- **Bilingual** — `language_hints: [en, zh]` with per-token language tags
- **Speaker diarization** — automatic speaker detection, labels as `Speaker 0`, `Speaker 1`, etc.

Output format:
```
Speaker 0:
[en] So I was thinking about the data center project...

Speaker 1:
[zh] 对，我觉得我们需要重新考虑一下方案。
[en] The timeline is too aggressive.
```

### Speaker Confirmation (`speaker.py`)

After transcription, Vox shows a preview of each detected speaker:

```
Found 2 speaker(s) in transcript:

  Speaker 0:
    "So I was thinking about the data center project..."
  Name [Jetson]: ↵

  Speaker 1:
    "对，我觉得我们需要重新考虑一下方案."
  Name [Terry Chen]: ↵
```

- Pre-fills suggestions from the names you provided
- You can override any suggestion by typing a different name
- Replaces all `Speaker N:` labels in the transcript with confirmed names

### Contact Resolution (`contacts.py`)

When you type `vox record terry`, Vox resolves the name:

1. **Exact match** (case-insensitive) against `PRM/Relationships/**/*.md` filenames
   - `terry` → matches `Terry Chen.md` → uses "Terry Chen"
2. **Fuzzy match** via `difflib.get_close_matches` (threshold 0.5)
   - `terr` → "Did you mean Terry Chen? [Y/n]"
3. **New contact** — offers to create a stub card at `PRM/Relationships/Name.md`

### Analysis (`analyzer.py`)

- Writes transcript + prompt to a temp file
- Runs `codex exec <tmpfile>` with 5-minute timeout
- Analysis prompt (`default_analysis_prompt.txt`) extracts:
  - Key Themes
  - Decisions Made
  - Action Items (with `- [ ]` checkbox format)
  - Open Questions
  - Key Insights
  - Relationship Notes
- **Non-fatal** — if codex is missing or fails, the note is created with a placeholder

### Obsidian Integration (`obsidian.py`)

**Conversation note** — created at `Conversations/YYYY-MM-DD Display Name.md`:

```markdown
---
date: 2026-03-23
people: [[Terry Chen]]
tags: #conversation
---

## Transcript

[[Transcripts/2026-03-23-terry-chen.md]]

## Analysis

### Key Themes
- ...
```

**Conflict handling** — if the note already exists:
- `[o]verwrite` — replace entirely
- `[a]ppend analysis` — keep transcript, replace analysis section
- `[s]kip` — do nothing

**Daily note** — finds or creates `Calendar/YYYY-MM-DD.md`:
- Prefers exact `YYYY-MM-DD.md`; also matches suffixed files like `2026-03-09 (Terry Chat).md`
- Uses `Templates/Daily Note Template.md` as template for new notes
- Appends `- [[YYYY-MM-DD Display Name]]` to the `## Conversations` section
- **Idempotent** — skips if link already present

### Hooks (`hooks.py`)

Set `post_process_hook` in config to a script path. Vox calls it after all outputs are created, with these environment variables:

| Variable | Example |
|----------|---------|
| `VOX_DATE` | `2026-03-23` |
| `VOX_PEOPLE` | `Terry Chen` |
| `VOX_NOTE_PATH` | `/Users/you/My Vault/Conversations/2026-03-23 Terry Chen.md` |
| `VOX_AUDIO_PATH` | `/Users/you/Voice/archive/2026/03/2026-03-23-terry-chen.m4a` |
| `VOX_TRANSCRIPT_PATH` | `/Users/you/My Vault/Conversations/Transcripts/2026-03-23-terry-chen.md` |

60-second timeout. Non-fatal on failure.

---

## File Structure

```
~/Voice/archive/
└── 2026/
    └── 03/
        ├── 2026-03-21-terry-chen.m4a
        ├── 2026-03-23-robox-sync.m4a
        └── 2026-03-23-产品想法.m4a

~/My Vault/
├── Conversations/
│   ├── 2026-03-21 Terry Chen.md
│   ├── 2026-03-23 RoboX Sync.md
│   ├── 2026-03-23 产品想法.md
│   └── Transcripts/
│       ├── 2026-03-21-terry-chen.txt
│       ├── 2026-03-23-robox-sync.txt
│       └── 2026-03-23-产品想法.txt
├── Calendar/
│   ├── 2026-03-21.md        ← has [[2026-03-21 Terry Chen]]
│   └── 2026-03-23.md        ← has [[2026-03-23 RoboX Sync]], [[2026-03-23 产品想法]]
└── PRM/
    └── Relationships/
        ├── Terry Chen.md
        └── Tuo Liu.md
```

---

## Naming Conventions

| Thing | Format | Example |
|-------|--------|---------|
| Audio file | `YYYY-MM-DD-slug.m4a` | `2026-03-23-terry-chen.m4a` |
| Transcript | `YYYY-MM-DD-slug.txt` | `2026-03-23-terry-chen.txt` |
| Conversation note | `YYYY-MM-DD Display Name.md` | `2026-03-23 Terry Chen.md` |
| Daily note | `YYYY-MM-DD.md` | `2026-03-23.md` |
| Archive subdir | `YYYY/MM/` | `2026/03/` |

Slugs: lowercase, hyphens for spaces, CJK preserved, emoji/special chars stripped.

---

## Project Source

```
vox/
├── vox/
│   ├── __init__.py
│   ├── cli.py              # Entry point — init, record, process subcommands
│   ├── config.py            # ~/.vox/config.yaml load/save, path helpers
│   ├── naming.py            # Slug generation, date formatting, filename builders
│   ├── recorder.py          # sox recording, ffmpeg conversion
│   ├── transcriber.py       # Soniox API (TLS 1.2, retry, cleanup)
│   ├── speaker.py           # Speaker label detection, interactive confirmation
│   ├── contacts.py          # PRM/Relationships fuzzy matching, stub creation
│   ├── obsidian.py          # Conversation note, transcript save, daily note linking
│   ├── analyzer.py          # codex exec wrapper
│   └── hooks.py             # Post-process hook runner
├── pyproject.toml
├── default_analysis_prompt.txt
├── MIGRATION.md             # One-time migration playbook for existing files
└── README.md
```

---

## Error Handling

| Scenario | What happens |
|----------|-------------|
| Transcription fails | Audio is already archived. Prints path. Retry with `vox process`. |
| codex fails or missing | Note created with `## Analysis` placeholder. Not fatal. |
| sox records empty file | Checks size < 1KB, aborts with mic error message. |
| Daily note link already exists | Skips silently (idempotent). |
| Conversation note already exists | Prompts: overwrite / append analysis / skip. |
| Contact not found in PRM | Fuzzy match suggestion, or create stub card. |
| Hook script fails | Logs error, continues. Non-fatal. |

---

## Migration

If you have existing recordings and conversation files scattered across your system, see **[MIGRATION.md](./MIGRATION.md)** for the one-time reorganization playbook.
