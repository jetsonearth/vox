# Date Corrections for Misdated 2026-03-18 Files

The previous migration agent couldn't detect original dates and dumped everything under 2026-03-18. Below is the verified correction map with actual dates extracted from transcript headers (e.g. "2025年10月22日 13:20").

## Instructions

For each entry below, do ALL of the following:

1. **Rename transcript** in `~/My Vault/Conversations/Transcripts/` (change date prefix)
2. **Rename conversation note** in `~/My Vault/Conversations/` (change date prefix)
3. **Update frontmatter** `date:` field inside the conversation note to the correct date
4. **Update transcript wikilink** `[[Transcripts/...]]` inside the conversation note to point to the renamed transcript
5. **Rename audio file** in `~/Voice/archive/` — move from `2026/03/` to correct `YYYY/MM/` subdirectory
6. **Remove the wrong link** from `~/My Vault/Calendar/2026-03-18.md`
7. **Add correct link** to the appropriate `~/My Vault/Calendar/YYYY-MM-DD.md` (create daily note from template if it doesn't exist)

If a file doesn't exist at the expected path, skip it silently.

---

## Correction Map

### Files that are ACTUALLY from 2026-03-18 (keep as-is, DO NOT rename)

These are correctly dated. Leave them alone but keep their links in Calendar/2026-03-18.md:

- `顺泰康源` → 2026-03-18 (no transcript content, audio path confirms date)
- `比泰利电子` → 2026-03-18
- `拓哥` → 2026-03-18
- `思考：Sonnet product feature` → 2026-03-18 (audio only, no conversation note)
- `dara` → 2026-03-18 (audio only, transcript is placeholder)
- `Michael Germany eng` → 2026-03-18

### Files that need date correction

| Display Name | Wrong Date | Correct Date | Evidence |
|---|---|---|---|
| 柯宇 11 | 2026-03-18 | **2025-10-22** | Transcript: "2025年10月22日 13:20" |
| 凡哥 roadtrip strategy | 2026-03-18 | **2025-10-15** | Transcript: "2025年10月15日 23:29" |
| Huey 2 | 2026-03-18 | **2025-10-28** | Transcript: "2025年10月28日 18:46" |
| Dara 2 | 2026-03-18 | **2025-12-07** | Transcript: "2025年12月07日 22:07" |
| 德国 Zillou | 2026-03-18 | **2025-10-18** | Transcript: "2025年10月18日 11:23" |
| 健诚 | 2026-03-18 | **2025-10-10** | Transcript: "2025年10月10日 19:39" |
| 黎巴嫩 超市 + 1MW仓储（讲AI需求）| 2026-03-18 | **2025-10-18** | Transcript: "2025年10月18日 13:31" |
| 展会takeaway（B2B + Sonnet）| 2026-03-18 | **2025-10-18** | Transcript: "2025年10月18日 15:38" |
| 印度 电子设计 | 2026-03-18 | **2025-10-16** | Transcript: "2025年10月16日 22:06" |
| New Recording 83 | 2026-03-18 | **2025-08-31** | Transcript: "2025年08月31日 08:19" |
| New Recording 96 | 2026-03-18 | **2025-10-16** | Transcript: "2025年10月16日 22:06" |
| 西班牙电线 | 2026-03-18 | **2025-10-18** | Transcript header |
| 葡萄牙进口商 | 2026-03-18 | **2025-10-16** | Transcript header |
| 纯姐 dinner | 2026-03-18 | **2025-12-02** | Transcript header |
| 橄醇 | 2026-03-18 | **2025-12-02** | Transcript header |
| 妈 越南地推 | 2026-03-18 | **2025-10-20** | Transcript header |
| 土耳其 进口 construction | 2026-03-18 | **2025-10-17** | Transcript header |
| 南非 进口 | 2026-03-18 | **2025-10-16** | Transcript header |
| 以色列 2个 purchasing mngr | 2026-03-18 | **2025-10-16** | Transcript header |
| 中亚贸易商 | 2026-03-18 | **2025-10-15** | Transcript header |
| ed-miller-post-interview-synthesis | 2026-03-18 | **2026-02-01** | Conversation note content |
| Tuo 2-12-26 zho | 2026-03-18 | **2026-02-12** | Filename contains date |
| Tomer 以色列采购 | 2026-03-18 | **2025-10-15** | Transcript header |
| Terry 3 | 2026-03-18 | **2026-03-09** | Already exists as 2026-03-09 Terry 3.md |
| SZ Gov <> Sonnet | 2026-03-18 | **2025-12-19** | Transcript header |
| Pakistan buyer | 2026-03-18 | **2025-10-15** | Transcript header |
| Omer Turkish Electric Appliances Importer | 2026-03-18 | **2025-10-16** | Transcript header |
| Manesh 香港进口商卖中美 | 2026-03-18 | **2025-10-16** | Transcript header |
| James 澳大利亚一人团队sourcing | 2026-03-18 | **2025-10-16** | Transcript header |
| Huey | 2026-03-18 | **2025-10-28** | Transcript header |
| Huey @ Four Seasons Lobby | 2026-03-18 | **2025-12-09** | Transcript header |
| Fervid | 2026-03-18 | **2025-12-12** | Transcript header |

---

## Detailed Rename Operations

For each corrected file, here are the exact operations. Slug = lowercase-hyphenated version of the display name.

### Example: 柯宇 11 (2025-10-22)

```bash
# Transcript
mv "~/My Vault/Conversations/Transcripts/2026-03-18-柯宇-11.md" \
   "~/My Vault/Conversations/Transcripts/2025-10-22-柯宇-11.md"

# Conversation note
mv "~/My Vault/Conversations/2026-03-18 柯宇 11.md" \
   "~/My Vault/Conversations/2025-10-22 柯宇 11.md"
# Then update inside the file:
#   date: 2025-10-22
#   [[Transcripts/2025-10-22-柯宇-11.md]]

# Audio (if exists)
mkdir -p "~/Voice/archive/2025/10"
mv "~/Voice/archive/2026/03/2026-03-18-柯宇-11.m4a" \
   "~/Voice/archive/2025/10/2025-10-22-柯宇-11.m4a"

# Calendar: remove [[2026-03-18 柯宇 11]] from Calendar/2026-03-18.md
# Calendar: add [[2025-10-22 柯宇 11]] to Calendar/2025-10-22.md
```

Apply the same pattern for all 27 entries in the correction table above.

---

## Calendar/2026-03-18.md Cleanup

After corrections, the only conversation links that should remain in this file are:

```markdown
## Conversations
- [[2026-03-18 顺泰康源]]
- [[2026-03-18 比泰利电子]]
- [[2026-03-18 拓哥]]
- [[2026-03-18 思考：Sonnet product feature]]
- [[2026-03-18 dara]]
- [[2026-03-18 Michael Germany eng]]
```

All other 27 links should be REMOVED from this file and added to their correct daily notes.

---

## Special Cases

- **Terry 3**: A conversation note `2026-03-09 Terry 3.md` already exists at the correct date. The calendar link `[[2026-03-18 Terry 3]]` should become `[[2026-03-09 Terry 3]]`. Check if duplicate notes exist and merge if needed.
- **Tuo 2-12-26 zho**: Has date in original name. Correct date is 2026-02-12. Check if `2026-02-12 Tuo 2-12-26 zho.md` already exists (it might — the first migration may have handled this one).
- **ed-miller-post-interview-synthesis**: This is an analysis document, not a standard conversation note. Still rename to `2026-02-01 ed-miller-post-interview-synthesis.md`.
- **Huey** and **Huey 2**: Both from 2025-10-28 — they are separate recordings from the same day. Keep both.
- **New Recording 83** and **New Recording 96**: Generic names. Consider renaming to something descriptive after listening, but for now just fix the dates.
- **dara** vs **Dara 2**: `dara` is actually from 2026-03-18 (keep). `Dara 2` is from 2025-12-07 (fix).

## Verification

After all corrections:
1. No files in `~/My Vault/Conversations/` should have `2026-03-18` prefix except the 6 that truly belong there
2. No files in `~/My Vault/Conversations/Transcripts/` should have `2026-03-18` prefix except those same 6
3. `Calendar/2026-03-18.md` should have exactly 6 conversation links
4. Each corrected daily note should have its conversation link added
5. All `[[Transcripts/...]]` wikilinks in conversation notes should point to existing files
