# Vox — Voice Recording Pipeline Automation

## Context

Jetson's current workflow is manual: record → run soniox.py → paste into Claude/GPT → save to Obsidian. Vox automates the entire chain into a single command. PRM (Bondfyre) is a separate project at `/Users/ZhaobangJetWu/studio-kensense/Bondfyre` — Vox connects to it via a post-process hook but does not own PRM logic.

## Pipeline: What Happens

```
vox record terry → 录音 → 停止 → speaker确认 → 转录 → 分析 → 归档
```

**4 outputs per conversation:**

| # | Output | Location |
|---|--------|----------|
| 1 | Audio | `~/Voice/archive/2026/03/2026-03-23-terry-gridmind.m4a` |
| 2 | Transcript | `~/My Vault/Conversations/Transcripts/2026-03-23-terry-gridmind.md` |
| 3 | Conversation Note | `~/My Vault/Conversations/2026-03-23 Terry Gridmind.md` |
| 4 | Daily note ref | `[[2026-03-23 Terry Gridmind]]` appended to `Calendar/2026-03-23.md` |

Plus optional Bondfyre hook for people card update.

## Project Structure

```
/Users/ZhaobangJetWu/studio-kensense/vox/
├── vox/
│   ├── __init__.py
│   ├── cli.py              # Entry point, argparse, pipeline orchestration
│   ├── config.py           # Load/save ~/.vox/config.yaml
│   ├── naming.py           # Slug generation, date formatting
│   ├── recorder.py         # sox wrapper for audio recording
│   ├── transcriber.py      # Soniox API (adapted from RoboX version)
│   ├── speaker.py          # Speaker label confirmation + replacement
│   ├── contacts.py         # Fuzzy match vault contacts
│   ├── obsidian.py         # Note creation, daily note management
│   ├── analyzer.py         # codex exec wrapper
│   └── hooks.py            # Post-process hook runner
├── pyproject.toml
└── default_analysis_prompt.txt
```

## Implementation Order

### Phase 1: Foundation (naming.py, config.py, pyproject.toml)
- `naming.py`: slug generation (`make_slug`), date formatting (`make_daily_note_filename` → `YYYY-MM-DD`), filename builders
- `config.py`: load/save `~/.vox/config.yaml`, path resolution helpers
- `pyproject.toml`: deps = requests, PyYAML, urllib3. Entry point: `vox = "vox.cli:main"`

### Phase 2: Core Pipeline (transcriber.py, speaker.py, recorder.py)
- `transcriber.py`: Adapt from `/Users/ZhaobangJetWu/studio-kensense/RoboX/soniox.py` — keep `build_session()` (TLS 1.2 + retry), `upload_audio()`, `render_tokens()`, `try/finally` cleanup. Remove argparse/file-moving. Single `transcribe(audio_path, cfg) → str` function
- `speaker.py`: Parse transcript for speaker blocks, show first 2 sentences per speaker, interactive confirmation, regex replace labels
- `recorder.py`: `sox -d -r 44100 -c 1` to temp WAV, convert to M4A if possible, graceful Ctrl+C/Enter stop

### Phase 3: Obsidian Integration (obsidian.py, contacts.py)
- `obsidian.py`: Build frontmatter (matching existing vault pattern: date, people as `[[wikilink]]`, projects, tags), create conversation note with `[[Transcripts/...]]` wikilink, `ensure_daily_note()` from template, `append_to_conversations_section()`
- `contacts.py`: Recursive scan of `PRM/Relationships/` for .md files, fuzzy match with `difflib`, create stub card for new people

### Phase 4: Analysis (analyzer.py, default prompt)
- `analyzer.py`: Write prompt+transcript to temp file, pipe to `codex exec` via stdin, 5 min timeout, return analysis text
- `default_analysis_prompt.txt`: Structured prompt (Key Themes, Decisions, Action Items, Open Questions, etc.)

### Phase 5: Glue (cli.py, hooks.py)
- `cli.py`: 3 subcommands — `init`, `record`, `process`. `run_pipeline()` orchestrates steps 1-8
- `hooks.py`: Run optional post-process script with env vars (VOX_DATE, VOX_PEOPLE, VOX_NOTE_PATH, etc.)
- `vox init`: Ask name, vault path (create if no Obsidian), Soniox key, check sox/codex, create folders + config

## Commands

```bash
vox init                                    # Setup wizard
vox record terry                            # 1-on-1 with Terry
vox record --solo "产品想法"                 # Brain dump (no people card)
vox record "RoboX Sync" --speakers terry,tuo,huey  # Multi-person
vox process ~/Downloads/file.m4a --speaker terry    # Existing file
```

## Key Files to Reuse
- **RoboX soniox.py** (`/Users/ZhaobangJetWu/studio-kensense/RoboX/soniox.py`): `build_session()`, `TLS12HttpAdapter`, `upload_audio()` with retry, `render_tokens()`, cleanup pattern
- **Daily Note Template** (`~/My Vault/Templates/Daily Note Template.md`): copied for new daily notes
- **Existing conversation note format** (`~/My Vault/Conversations/2026-03-16 Terry (Gridmind).md`): frontmatter schema reference

## Error Handling
- Transcription fails → audio is already archived, print path, user can retry with `vox process`
- codex fails → note created with `## Analysis` placeholder, not a fatal error
- sox records empty file → check size, abort with mic error message
- Daily note link already present → skip silently (idempotent)
- Conversation note exists → prompt: overwrite / append analysis / skip

## Verification
1. `pip install -e /Users/ZhaobangJetWu/studio-kensense/vox/` → `vox` command available
2. `vox init` → creates `~/.vox/`, `~/Voice/archive/`, vault folders
3. `vox process <existing .m4a> --speaker terry` → produces all 4 outputs
4. Check `~/My Vault/Conversations/` for new note with correct frontmatter
5. Check `~/My Vault/Calendar/` for daily note with appended link
6. `vox record terry` → records, then same pipeline

---

## Phase 2: Speaker Diarization + Voiceprint Recognition

### Problem
Soniox speaker diarization 准确率低且不支持声纹识别。每次转录后都要手动将 "Speaker 0/1" 映射为实际人名。

### Goal
用 pyannote 替换 Soniox diarization + SpeechBrain ECAPA-TDNN 声纹识别，实现 speaker label 全自动化。

**约束**: 保留 Soniox ASR（文字质量 OK）、Apple Silicon Mac (MPS)、中英双语、支持 1v1 和多人。

### Architecture

```
Audio ──→ Soniox ASR (diarization OFF) ──→ tokens + timestamps
  │
  └────→ pyannote speaker-diarization-3.1 ──→ speaker segments
                                                    │
              ┌─────────────────────────────────────┘
              ▼
         Align tokens to segments (by timestamp overlap)
              │
              ▼
         SpeechBrain ECAPA-TDNN embeddings per speaker
              │
              ▼
         Match vs enrolled voiceprints (cosine similarity)
              │
              ├─ high confidence → auto-label
              └─ low confidence  → interactive confirm → auto-learn
```

**Hybrid approach**: pyannote for diarization (best pipeline), SpeechBrain ECAPA-TDNN for speaker embeddings (best quality for verification/identification).

### Implementation Steps

#### Step 1: Dependencies (`pyproject.toml`)
Add optional `[diarize]` group:
```toml
[project.optional-dependencies]
diarize = ["torch>=2.0", "torchaudio>=2.0", "pyannote-audio>=3.3", "speechbrain>=1.0", "numpy>=1.24"]
```
Code does lazy import with helpful error if missing.

#### Step 2: Structured transcript data (`vox/transcriber.py`)
- Add `Token` and `TranscriptResult` dataclasses (text, speaker, language, start_ms, end_ms)
- `transcribe()` returns `TranscriptResult` instead of `str` (`.text` preserves old behavior)
- Parse `start_ms`/`end_ms` from Soniox tokens (they return these but we currently ignore them)
- Add `enable_speaker_diarization` config option (disable Soniox diarization when pyannote is used)

#### Step 3: Update callers (`vox/cli.py`)
- `_run_pipeline()`: `result = transcribe(...)`, `transcript = result.text` — no behavior change yet

#### Step 4: Diarization module (`vox/diarize.py` — new)
- Load pyannote `speaker-diarization-3.1` pipeline (module-level cache, ~1GB model)
- Auto-detect MPS/CPU device
- `diarize(audio_path, cfg, num_speakers=None) → list[DiarSegment]`
- DiarSegment: `start_sec`, `end_sec`, `speaker` (e.g. "SPEAKER_00")

#### Step 5: Alignment module (`vox/align.py` — new)
- `align_tokens_to_segments(tokens, segments) → list[AlignedToken]`
- For each token, find pyannote segment with max timestamp overlap → assign speaker
- Fallback: proportional alignment if timestamps missing
- `render_aligned_tokens(aligned) → str` (same output format as current `render_tokens`)

#### Step 6: Voiceprint module (`vox/voiceprint.py` — new)
- Use **SpeechBrain ECAPA-TDNN** (`speechbrain/spkrec-ecapa-voxceleb`) for embeddings
- Storage: `~/.vox/voiceprints/{name}_NNN.npy` + `index.json`
- `extract_speaker_embedding(audio, segments, speaker_label) → np.ndarray` (duration-weighted centroid)
- `enroll(name, embedding, source)` — append to voiceprint DB
- `match_speakers(audio, segments) → {label: VoiceprintMatch | None}` — cosine similarity, threshold 0.65
- `enroll_from_conversation(audio, segments, label, name)` — auto-learn from confirmed labels

#### Step 7: Config updates (`vox/config.py`)
- New keys: `hf_token`, `enable_diarization: true`, `diarization_device: "auto"`, `voiceprint_threshold: 0.65`, `auto_learn_voiceprints: true`
- `voiceprints_dir()` helper, update `ensure_dirs()`

#### Step 8: Auto-labeling (`vox/speaker.py`)
- `auto_label_speakers(transcript, matches)` — apply high-confidence voiceprint matches
- `confirm_speakers_with_voiceprint(transcript, matches, expected_names)` — interactive with pre-filled voiceprint guesses

#### Step 9: Pipeline integration (`vox/cli.py`)
- Wire into `_run_pipeline()`: transcribe → diarize → align → voiceprint match → auto-label / confirm
- Auto-learn: after confirmation, `enroll_from_conversation()` for future sessions
- `--no-diarize` flag to fall back to Soniox diarization
- New `vox enroll <name> <audio_file>` subcommand

#### Step 10: Tests
- `test_diarize.py` — mock pyannote pipeline
- `test_align.py` — synthetic tokens + segments alignment
- `test_voiceprint.py` — enrollment, matching, threshold logic
- Update `test_transcriber.py` for `TranscriptResult`

### Key Files to Modify
- `vox/transcriber.py` — return structured data with timestamps
- `vox/cli.py` — pipeline orchestration + enroll command
- `vox/speaker.py` — auto-labeling functions
- `vox/config.py` — new config keys
- `pyproject.toml` — optional deps

### New Files
- `vox/diarize.py` — pyannote wrapper
- `vox/align.py` — token-to-segment alignment
- `vox/voiceprint.py` — SpeechBrain ECAPA-TDNN embedding extraction, enrollment, matching

### Verification
1. `vox enroll "Jetson" sample_audio.m4a` — confirm voiceprint saved to `~/.vox/voiceprints/`
2. `vox record terry` — verify pyannote diarization runs, speakers auto-labeled by voiceprint
3. Record with unknown speaker — verify falls back to interactive confirmation, then auto-learns
4. `vox record terry --no-diarize` — verify Soniox fallback still works
5. Run full test suite: `pytest tests/`
