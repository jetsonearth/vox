# Vox Migration Playbook

Reorganize all recordings, transcripts, and conversation files across the entire system into the clean structure that Vox expects.

## Target Structure

```
~/Voice/archive/
└── YYYY/MM/
    └── YYYY-MM-DD-slug.m4a          # All audio archived here

~/My Vault/
├── Conversations/
│   ├── YYYY-MM-DD Display Name.md   # Conversation notes (standardized naming)
│   └── Transcripts/
│       └── YYYY-MM-DD-slug.txt      # Plain text transcripts
├── Calendar/
│   └── YYYY-MM-DD.md                # Daily notes with [[conversation]] links
└── PRM/Relationships/               # People cards (unchanged)
```

## Current State (as of 2026-03-23)

| Location | What's There | Count |
|----------|-------------|-------|
| `~/Downloads/` | Scattered .m4a conversation recordings | ~12 conversation files |
| `~/My Vault/Conversations/` | 88 .md notes, 3 naming formats | 88 |
| `~/My Vault/Conversations/Transcripts/` | 43 .m4a + 42 .docx + 7 .txt (mixed) | 92 |
| `~/studio-kensense/robox/Calls/results/` | RoboX pipeline: 9 .m4a + 7 .txt under `{team,buyer}/*/` (paired) | 16 |
| `~/studio-kensense/transcription/results/` | Shared transcription output (e.g. `partner/…`): 67 .m4a + 68 .txt | 135 |
| `~/studio-kensense/sonnet/transcription/results/` | Sonnet buyer/partner calls (nested under e.g. `2025 Buyer Calls/`): 90 .m4a + 91 .txt | 181 |
| `~/Voice/` | Empty | 0 |

**Note:** On disk the RoboX repo folder is `robox` (lowercase), not `RoboX`. Call output also lives under `**/transcription/results` (studio root + Sonnet), not only `**/Calls/results`.

---

## Phase 1: Audio Consolidation

Move all conversation audio to `~/Voice/archive/YYYY/MM/`.

### 1a. Audio from `~/My Vault/Conversations/Transcripts/`

43 .m4a files currently living alongside transcripts. Move to archive.

```python
# For each .m4a in ~/My Vault/Conversations/Transcripts/:
# 1. Infer date from filename (e.g., "Phanos H. @ 2050 Materials 1-19-26.m4a" → 2026-01-19)
# 2. Generate slug from name portion
# 3. Move to ~/Voice/archive/2026/01/2026-01-19-phanos-h-2050-materials.m4a
# 4. DO NOT delete yet — log the mapping (old_path → new_path) for updating note embeds
```

**Files to move:**
- All 43 `.m4a` files from `~/My Vault/Conversations/Transcripts/`
- Pattern: most are named `Person Name M-D-YY.m4a` or `Description.m4a`

### 1b. Audio from `~/Downloads/`

Conversation recordings mixed with other downloads.

```
# Known conversation recordings in Downloads (not the AI Library music files):
# - Phanos H. @ 2050 Materials 1-19-26.m4a
# - (and others with person names + dates)
#
# Skip: ~/Downloads/AI Library/ (music/sfx, not conversations)
# Skip: any file < 500KB (likely not a real recording)
#
# For each conversation .m4a:
# 1. Infer date from filename
# 2. Move to ~/Voice/archive/YYYY/MM/YYYY-MM-DD-slug.m4a
```

### 1c. Audio from pipeline result folders (RoboX + studio transcription + Sonnet)

Besides vault and Downloads, conversation `.m4a` files also sit under automation output trees. **Treat these as additional sources** (same date/slug rules as elsewhere):

| Root | Role |
|------|------|
| `~/studio-kensense/robox/Calls/results/` | RoboX `team/` and `buyer/` call folders |
| `~/studio-kensense/transcription/results/` | Studio-wide transcription (e.g. `partner/Display Name M-D-YY/`) |
| `~/studio-kensense/sonnet/transcription/results/` | Sonnet pipeline (e.g. `2025 Buyer Calls/…`, other subfolders) |

```
# For each .m4a under the roots above (recursively):
# 1. Infer date from folder/filename (e.g. "Tuo 3-2-26", "Juan @ Ato 11-29-25")
# 2. COPY (don't move) to ~/Voice/archive/YYYY/MM/YYYY-MM-DD-slug.m4a
#    — pipelines and local scripts may still reference original paths.
#
# Example (RoboX):
# robox/Calls/results/team/Tuo 3-2-26/Tuo 3-2-26.m4a
# → ~/Voice/archive/2026/03/2026-03-02-tuo.m4a
```

**Finding other result folders (one-time):** Start from the known roots in the table above. To see if anything else exists under common folders (bounded depth), you can run:

```bash
find ~/Documents ~/Desktop ~/Downloads ~/Sonnet ~/projects ~/dev ~/code \
  -maxdepth 16 \
  \( -name node_modules -o -name .git -o -path '*/Downloads/AI Library' \) -prune -o \
  -type d \( -path '*/Calls/results' -o -path '*/calls/results' -o -path '*/transcription/results' \) -print 2>/dev/null | sort -u
```

Adjust the root list or `-maxdepth` as needed; avoid scanning your entire home directory.

---

## Phase 2: Transcript Standardization

Transcripts live as `.md` in `Conversations/Transcripts/` (content is plain text).

### 2a. Existing .txt files — rename to standard format

```
# 7 .txt files already in Transcripts/
# Rename to: YYYY-MM-DD-slug.txt
# Example: "Tuo 2-23-26.txt" → "2026-02-23-tuo.txt"
```

### 2b. .docx files — extract text, save as .txt

```
# 42 .docx files in Transcripts/ (named *_原文.docx)
# For each:
# 1. Extract plain text (python-docx or pandoc)
# 2. Save as YYYY-MM-DD-slug.txt
# 3. Keep .docx as backup (move to ~/Voice/archive/docx_backup/ or delete)
#
# Example: "Terry (Gridmind) 3-16-26_原文.docx" → "2026-03-16-terry-gridmind.txt"
```

### 2c. Pipeline transcripts — copy to vault

Same **result roots** as Phase 1c: `robox/Calls/results/`, `studio-kensense/transcription/results/`, `sonnet/transcription/results/`.

```
# For each call transcript .txt under those trees (skip *_analysis.md and other non-transcript files; vault uses .md):
# 1. Infer date + slug (align with the copied/archived .m4a for that call when possible)
# 2. COPY to ~/My Vault/Conversations/Transcripts/YYYY-MM-DD-slug.md
# 3. If two sources would collide on the same dest filename, disambiguate (e.g. suffix -robox, -sonnet-buyer)
#
# RoboX .txt is typically Speaker/[lang] from soniox.py; Sonnet/studio trees may use a single plain .txt per folder.
```

---

## Phase 3: Conversation Note Standardization

Rename all 88 notes to `YYYY-MM-DD Display Name.md` and fix frontmatter.

### Naming Patterns to Normalize

| Current Pattern | Example | Target |
|----------------|---------|--------|
| `YYYY-MM-DD Person (Context).md` | `2026-03-16 Terry (Gridmind).md` | `2026-03-16 Terry Gridmind.md` |
| `Person M-D-YY.md` | `Phanos H. @ 2050 Materials 1-19-26.md` | `2026-01-19 Phanos H 2050 Materials.md` |
| `Person Name.md` (no date) | `Fervid.md`, `美国买家.md` | Keep as-is OR infer date from file mtime |
| `Chinese_underscore_date.md` | `柯宇_2025-10-22_联合创始人会议分析.md` | `2025-10-22 柯宇 联合创始人会议分析.md` |
| Emoji in filename | `德国🇩🇪Zillou.md` | `德国 Zillou.md` (strip emoji) |

### Frontmatter Template

Every note should have this structure:

```yaml
---
date: YYYY-MM-DD
people: [[Person Name]]
tags: #conversation
---

## Transcript

[[Transcripts/YYYY-MM-DD-slug.md]]

## Analysis

(existing analysis content, or placeholder)
```

### Steps per note:

```
# For each .md in ~/My Vault/Conversations/:
# 1. Parse existing frontmatter (if any)
# 2. Extract/infer date from filename or frontmatter
# 3. Extract people names from frontmatter or filename
# 4. Rename file to "YYYY-MM-DD Display Name.md"
# 5. Update frontmatter to standard format
# 6. Update transcript embed to point to new .md filename
# 7. Preserve any existing ## Analysis content
```

### Special cases:

- **Analysis-only files** (e.g., `柯宇_2025-10-22_联合创始人会议分析.md`, `ed-miller-post-interview-synthesis.md`): These are analysis documents, not conversation notes. Keep them but rename to standard format.
- **README.md, Index.md**: Skip — not conversation notes.
- **Duplicate/related notes** (e.g., `Huey.md`, `Huey 2.md`, `Huey 3-3-26 (RoboX Update).md`): Treat as separate conversations. Undated ones → infer from mtime.

---

## Phase 4: Daily Note Backfill

Link conversation notes to their corresponding daily notes.

```
# For each conversation note with a valid date:
# 1. Find or create ~/My Vault/Calendar/YYYY-MM-DD.md
# 2. If creating, use ~/My Vault/Templates/Daily Note Template.md as template
# 3. Find the "## Conversations" section
# 4. Append "- [[YYYY-MM-DD Display Name]]" if not already present
# 5. Idempotent — skip if link exists
```

### Daily note filename format: `YYYY-MM-DD.md` (optional suffix)

Examples:
- `2026-03-21` → `2026-03-21.md`
- `2025-10-22` → `2025-10-22.md`

**Note:** Some dailies use a suffix, e.g. `2026-03-03 （Huey 交流、马士基 call）.md`. Match with `glob("YYYY-MM-DD*.md")` and prefer exact `YYYY-MM-DD.md` when present.

---

## Phase 5: Cleanup

### 5a. Remove moved .m4a files from Transcripts/

After Phase 1 completes and all note embeds are updated:
```
# Delete all .m4a files from ~/My Vault/Conversations/Transcripts/
# (they now live in ~/Voice/archive/)
```

### 5b. Archive or delete .docx backups

```
# Option A: Move to ~/Voice/archive/docx_backup/
# Option B: Delete (plain text versions now in Transcripts/)
```

### 5c. Verify no broken embeds

```
# Scan all .md files in Conversations/ for ![[...]] embeds
# Check that each referenced file exists in Transcripts/
# Report any broken links
```

---

## Execution Notes

One-time cleanup: follow the phases manually or with a **throwaway script**; nothing here needs to live in the `vox` CLI.

- **DRY RUN FIRST**: List planned moves/renames before executing.
- **Backup**: Snapshot or copy the vault (and any pipeline folders you will delete from) before destructive steps.
- **Idempotent**: If you script it, skipping already-copied destinations keeps reruns safe.
- **Log**: Keeping a text log (e.g. `~/.vox/migration_log.txt`) makes embed fixes easier.
- **Pipeline roots**: Include `robox/Calls/results`, `transcription/results` (studio + Sonnet), plus any extra dirs you discover with the `find` above; track them in `migration_map.yaml` if you use one.
- **Dependencies**: `pip install python-docx` for .docx → .txt conversion (Phase 2b).

## File Mapping Reference

Optional: keep a mapping file at `~/.vox/migration_map.yaml` while you work (helps renames and embed updates):

```yaml
audio:
  "~/My Vault/Conversations/Transcripts/Phanos H. @ 2050 Materials 1-19-26.m4a":
    dest: "~/Voice/archive/2026/01/2026-01-19-phanos-h-2050-materials.m4a"
    date: 2026-01-19
transcripts:
  "~/My Vault/Conversations/Transcripts/Terry (Gridmind) 3-16-26_原文.docx":
    dest: "~/My Vault/Conversations/Transcripts/2026-03-16-terry-gridmind.md"
    date: 2026-03-16
notes:
  "~/My Vault/Conversations/Phanos H. @ 2050 Materials 1-19-26.md":
    dest: "~/My Vault/Conversations/2026-01-19 Phanos H 2050 Materials.md"
    date: 2026-01-19
```
