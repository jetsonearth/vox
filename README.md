# Vox

Voice recording pipeline automation. One command to record, transcribe, analyze, and archive a conversation into Obsidian.

## What It Does

```
vox record terry → record → stop → transcribe → diarize → voiceprint → analyze → vault
```
With **diarization enabled**, speakers are auto-identified by voiceprint (no manual mapping needed). Without it, the transcript keeps Soniox **`Speaker 1`, `Speaker 2`, …** labels — use **`--name-speakers`** for optional interactive renaming.

Every conversation produces **4 outputs**:

| # | Output | Location |
|---|--------|----------|
| 1 | Audio | `~/Voice/archive/2026/03/2026-03-23-terry-chen.m4a` |
| 2 | Transcript | `~/My Vault/Conversations/Transcripts/2026-03-23-terry-chen.txt` |
| 3 | Conversation Note | `~/My Vault/Conversations/2026-03-23 Terry Chen.md` |
| 4 | Daily note link | `[[2026-03-23 Terry Chen]]` appended to `Calendar/2026-03-23.md` |

Plus an optional post-process hook (e.g. update Bondfyre people card).

---

## Install

```bash
# From the vox project directory
python3 -m venv .venv
.venv/bin/pip install -e .

# Optional: speaker diarization + voiceprint recognition
.venv/bin/pip install -e '.[diarize]'

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
| **pyannote + SpeechBrain** | Optional (diarization) | `pip install 'vox[diarize]'` |
| **HuggingFace token** | Required for diarization | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |

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
# soniox_transcript_timeout_sec: 18000  # Optional: seconds for GET …/transcript (default scales with duration)

# Speaker diarization & voiceprint (requires pip install 'vox[diarize]')
enable_diarization: false  # Set to true to use pyannote instead of Soniox diarization
hf_token: ""               # HuggingFace token (required for pyannote gated model)
diarization_device: auto   # auto (MPS > CPU), mps, or cpu
voiceprint_threshold: 0.65 # Cosine similarity threshold for confident match
auto_learn_voiceprints: true  # Auto-enroll voiceprints from confirmed speakers
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

# Optional: interactive speaker renaming (default is generic Speaker N labels)
vox record --solo "quick note" --name-speakers

# Non-interactive: set Soniox options on the command line (skips prompts after you stop recording)
vox record terry --language-hints en,zh --soniox-context "Q4 roadmap; acronyms: OKR, KPI"
```

**What happens step by step:**

1. **Record** — sox captures audio from default mic. Press **Enter** or **Ctrl+C** to stop.
2. **Archive audio** — Saved directly to `~/Voice/archive/YYYY/MM/YYYY-MM-DD-slug.m4a`
3. **Soniox options** — After recording stops, you are prompted (TTY only) for **languages** and optional **context** (same as `vox process`), then the file is uploaded. Use `--language-hints` / `--soniox-context` to skip those prompts.
4. **Transcribe** — Soniox async STT. When diarization is enabled, Soniox diarization is turned off (pyannote handles it).
5. **Diarize** *(if `enable_diarization: true`)* — pyannote segments the audio by speaker, tokens are aligned to segments.
6. **Voiceprint match** *(if diarization enabled)* — SpeechBrain matches each speaker against enrolled voiceprints. All confident? Auto-labels. Otherwise prompts for confirmation, then auto-learns.
7. **Save transcript** — Plain-text `Conversations/Transcripts/YYYY-MM-DD-slug.txt` with speaker names (or labels if no match).
8. **Speaker identification** *(fallback, no diarization)* — Only with **`--name-speakers`**: optional per-speaker prompts. Use `--no-diarize` to force this path.
9. **Analyze** — Pipes transcript + prompt through `codex exec`. Non-fatal if codex is missing.
10. **Create conversation note** — Markdown with frontmatter, transcript embed, analysis section.
11. **Link daily note** — Finds or creates `Calendar/YYYY-MM-DD.md`, appends `[[conversation]]` link.
12. **Run hook** — Optional post-process script with env vars.

### `vox process` — Process an existing audio file

For recordings you already have (e.g. from your phone, Downloads, another app):

```bash
# Optional --speaker for PRM + speaker-label suggestions (does not rename the archive)
vox process ~/Downloads/meeting.m4a --speaker terry

# Multiple speakers
vox process ~/Downloads/sync.m4a --speaker terry,tuo,huey

# --topic sets note title / archive slug; without it, the source filename (stem) is used
vox process ~/Downloads/call.m4a --speaker terry --topic "Gridmind Strategy"

# Explicit date override
vox process ~/Downloads/old-call.m4a --speaker terry --date 2026-03-21

# Non-interactive: set Soniox options on the command line (skips prompts)
vox process ~/Downloads/call.m4a --language-hints en,zh --soniox-context "Q4 roadmap; acronyms: OKR, KPI"
```

**Before transcribing**, `vox process` asks (TTY only) for **languages** in the recording (comma-separated ISO codes; Enter uses `language_hints` from `~/.vox/config.yaml`, usually `en` + `zh`) and optional **context** text. That string is sent to Soniox’s `context` field so the model can bias vocabulary, names, and domain terms ([create transcription API](https://soniox.com/docs/stt/api-reference/transcriptions/create_transcription)). Use `--language-hints` / `--soniox-context` to skip either prompt (e.g. scripts).

**Date detection** (in priority order):
1. `--date` flag (supports `YYYY-MM-DD` or `M-D-YY`)
2. Date in filename (e.g. `terry-3-21-26.m4a` → 2026-03-21)
3. File creation time (`st_birthtime` on macOS)
4. Today's date (last resort)

**`vox process`** **moves** the file into the archive (no duplicate in Downloads). `vox record` still writes straight into the archive.

**Naming:** Archived audio, transcript, and conversation note use **`--topic`** when you pass it. If you omit `--topic`, they follow the **input file’s name** (without `.m4a`). `--speaker` does not change that slug — it only fills `people` in the note and supplies suggestions when you use **`--name-speakers`**. If the filename already starts with the same `YYYY-MM-DD` as the detected recording date, that date is not repeated in the archive slug (so you don’t get `2026-03-22-2026-03-22-…`).

### `vox enroll` — Enroll a voiceprint

Requires `pip install 'vox[diarize]'` and `enable_diarization: true` in config.

```bash
# Enroll from an audio file (auto-detects if single speaker)
vox enroll "Jetson" ~/Voice/archive/2026/03/sample.m4a

# Multiple speakers in file — specify which one
vox enroll "Terry" meeting.m4a --speaker SPEAKER_01
```

Voiceprints are stored in `~/.vox/voiceprints/`. Once enrolled, speakers are auto-identified in future recordings by voice similarity.

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

Output format (Soniox default):
```
Speaker 0:
[en] So I was thinking about the data center project...

Speaker 1:
[zh] 对，我觉得我们需要重新考虑一下方案。
[en] The timeline is too aggressive.
```

### Speaker Diarization & Voiceprint (`diarize.py`, `align.py`, `voiceprint.py`)

When `enable_diarization: true` is set in config, Vox uses a **hybrid pipeline**:

1. **Soniox ASR** — transcription only (diarization turned off)
2. **pyannote speaker-diarization-3.1** — speaker segmentation (who spoke when)
3. **Token alignment** — each Soniox token is assigned to a pyannote segment by timestamp overlap
4. **SpeechBrain ECAPA-TDNN** — extracts speaker embeddings, matches against enrolled voiceprints

```
Audio ──→ Soniox ASR (diarization OFF) ──→ tokens + timestamps
  │
  └────→ pyannote diarization ──→ speaker segments
                                        │
              ┌─────────────────────────┘
              ▼
         Align tokens to segments (timestamp overlap)
              │
              ▼
         SpeechBrain ECAPA-TDNN embeddings per speaker
              │
              ▼
         Match vs enrolled voiceprints (cosine similarity)
              │
              ├─ all confident  → auto-label (no prompts)
              └─ any uncertain  → interactive confirm → auto-learn
```

Use `--no-diarize` on any command to fall back to Soniox diarization for that session.

Models auto-detect MPS (Apple Silicon) and fall back to CPU. First run downloads ~1GB of models.

### Speaker confirmation (`speaker.py`)

**Default:** no prompts; transcript stays `Speaker 1`, `Speaker 2`, … (good enough for analysis to infer roles).

With **`--name-speakers`**, in an interactive terminal you first see:

```
Map speakers to names? [Y/n]:
```

- **Enter** or **y** — continue to per-speaker prompts (below).
- **n** — leave the transcript as `Speaker 1`, `Speaker 2`, …

If you choose to map names, Vox shows a preview of each detected speaker:

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
- At any **`Name:`** prompt, type **`q`** (or **`quit`**) to stop mapping: speakers you already named stay renamed; **later** segments keep `Speaker 4`, `Speaker 5`, … (useful when diarization invents extra speakers)

If stdin is not a terminal and **`--name-speakers`** is set, Vox **skips** speaker prompts and keeps `Speaker N` labels (piped/non-interactive runs cannot prompt).

### Contact Resolution (`contacts.py`)

When you type `vox record terry`, Vox resolves the name:

1. **Exact match** (case-insensitive) against `PRM/Relationships/**/*.md` filenames
   - `terry` → matches `Terry Chen.md` → uses "Terry Chen"
2. **Your name** — if the string matches `user_name` in `~/.vox/config.yaml` (case-insensitive), it counts as you; no stub card
3. **Fuzzy match** via `difflib.get_close_matches` (default cutoff 0.4)
   - `terr` → "Did you mean Terry Chen? [Y/n]"
4. **New contact** — offers to create a stub card at `PRM/Relationships/Name.md`

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
# Transcript

[[Transcripts/2026-03-23-terry-chen.txt]]

---

# Analysis

## Key Themes
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
| `VOX_TRANSCRIPT_PATH` | `/Users/you/My Vault/Conversations/Transcripts/2026-03-23-terry-chen.txt` |

60-second timeout. Non-fatal on failure.

---

## File Structure

```
~/.vox/
├── config.yaml
└── voiceprints/             ← enrolled speaker voiceprints
    ├── index.json
    ├── Jetson_000.npy
    └── Terry_000.npy

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
│   ├── cli.py              # Entry point — init, record, process, enroll subcommands
│   ├── config.py            # ~/.vox/config.yaml load/save, path helpers
│   ├── naming.py            # Slug generation, date formatting, filename builders
│   ├── recorder.py          # sox recording, ffmpeg conversion
│   ├── transcriber.py       # Soniox API (TLS 1.2, retry, cleanup)
│   ├── speaker.py           # Speaker label detection, interactive + voiceprint confirmation
│   ├── diarize.py           # pyannote speaker-diarization-3.1 wrapper
│   ├── align.py             # Token-to-segment alignment by timestamp overlap
│   ├── voiceprint.py        # SpeechBrain ECAPA-TDNN enrollment & matching
│   ├── contacts.py          # PRM/Relationships fuzzy matching, stub creation
│   ├── obsidian.py          # Conversation note, transcript save, daily note linking
│   ├── analyzer.py          # codex exec wrapper
│   ├── hooks.py             # Post-process hook runner
│   └── ui.py                # Rich console helpers
├── pyproject.toml
├── default_analysis_prompt.txt
├── PLAN.md                  # Technical roadmap
└── README.md
```

---

## Error Handling

| Scenario | What happens |
|----------|-------------|
| Transcription fails | Audio is already archived. Prints path. Retry with `vox process`. |
| codex fails or missing | Note created with `# Analysis` placeholder. Not fatal. |
| sox records empty file | Checks size < 1KB, aborts with mic error message. |
| Daily note link already exists | Skips silently (idempotent). |
| Conversation note already exists | Prompts: overwrite / append analysis / skip. |
| Contact not found in PRM | Fuzzy match suggestion, or create stub card. |
| Hook script fails | Logs error, continues. Non-fatal. |

---

## Migration

If you have existing recordings and conversation files scattered across your system, see **[MIGRATION.md](./MIGRATION.md)** for the one-time reorganization playbook.
