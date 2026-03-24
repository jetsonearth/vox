"""Robust date inference for vault migration (filesystem + pipeline + backups)."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

# Dates when bulk migration/repair often touched files; prefer other evidence over these.
SUSPECT_MIGRATION_DATES: frozenset[date] = frozenset(
    date(2026, 3, d) for d in range(20, 29)
)

YMD = re.compile(r"(20\d{2})-(\d{1,2})-(\d{1,2})")
MDY = re.compile(r"(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})")
EMOJI_BLOCKS = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]+"
)


def strip_emojis(s: str) -> str:
    s = EMOJI_BLOCKS.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_ymd(s: str) -> date | None:
    m = YMD.search(s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_last_mdy(s: str) -> date | None:
    matches = list(MDY.finditer(s))
    if not matches:
        return None
    m = matches[-1]
    mo, da, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if yr < 100:
        yr += 2000 if yr < 70 else 1900
    nowy = date.today().year
    while yr > nowy + 2:
        yr -= 10
    try:
        return date(yr, mo, da)
    except ValueError:
        return None


def _stat_times(p: Path) -> tuple[float, float]:
    st = p.stat()
    birth = getattr(st, "st_birthtime", st.st_mtime)
    return birth, st.st_mtime


def file_artifact_dates(p: Path) -> tuple[date, date]:
    """Return (birth_date, mtime_date) for a path."""
    birth_ts, mtime_ts = _stat_times(p)
    return (
        datetime.fromtimestamp(birth_ts).date(),
        datetime.fromtimestamp(mtime_ts).date(),
    )


def is_suspect_migration_day(d: date) -> bool:
    return d in SUSPECT_MIGRATION_DATES


def collect_stat_dates(paths: Iterable[Path]) -> list[date]:
    out: list[date] = []
    for p in paths:
        if not p.is_file():
            continue
        try:
            bd, md = file_artifact_dates(p)
            out.append(bd)
            out.append(md)
        except OSError:
            continue
    return out


def best_date_from_stats(
    paths: Iterable[Path],
    *,
    prefer_not_suspect: bool = True,
) -> date | None:
    """Pick a representative calendar date from file birth/mtime, avoiding migration cluster."""
    dates: list[date] = collect_stat_dates(paths)
    if not dates:
        return None
    clean = [d for d in dates if not is_suspect_migration_day(d)]
    if prefer_not_suspect and clean:
        return min(clean)
    return min(dates)


_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_ENG_MON = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})\b",
    re.IGNORECASE,
)


def dates_from_text_blob(text: str) -> list[date]:
    found: list[date] = []
    for m in YMD.finditer(text):
        try:
            found.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    for m in _ENG_MON.finditer(text):
        mo = _MONTHS[m.group(1).lower()]
        da = int(m.group(2))
        yr = int(m.group(3))
        try:
            found.append(date(yr, mo, da))
        except ValueError:
            continue
    d = parse_last_mdy(text)
    if d:
        found.append(d)
    return found


def split_dated_transcript_filename(name: str) -> tuple[date, str] | None:
    m = re.match(r"^(20\d{2})-(\d{1,2})-(\d{1,2})-(.+)\.(txt|md)$", name)
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return d, m.group(4)


def normalize_match_key(s: str) -> str:
    s = strip_emojis(s)
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_pipeline_media_for_display(
    display: str,
    pipeline_roots: list[tuple[str, Path]],
) -> list[Path]:
    """Return .m4a / .txt under pipeline call folders that plausibly match this conversation."""
    nk = normalize_match_key(display)
    if len(nk) < 2:
        return []
    out: list[Path] = []
    for _tag, root in pipeline_roots:
        if not root.is_dir():
            continue
        for folder in root.rglob("*"):
            if not folder.is_dir():
                continue
            fn = normalize_match_key(folder.name)
            if not fn:
                continue
            if fn != nk and nk not in fn and fn not in nk:
                continue
            for pat in ("*.m4a", "*.txt"):
                for p in folder.glob(pat):
                    if p.name.endswith("_analysis.md"):
                        continue
                    if "analysis" in p.name.lower() and not p.name.endswith(".txt"):
                        continue
                    out.append(p)
    return out


def parse_date_from_path_string(s: str) -> date | None:
    d = parse_ymd(s)
    if d:
        return d
    return parse_last_mdy(s)


def pipeline_folder_dates_for_display(
    display: str,
    pipeline_roots: list[tuple[str, Path]],
) -> list[date]:
    """Parse M-D-YY / YYYY-MM-DD from matching pipeline folder paths and names."""
    nk = normalize_match_key(display)
    found: list[date] = []
    for _tag, root in pipeline_roots:
        if not root.is_dir():
            continue
        for folder in root.rglob("*"):
            if not folder.is_dir():
                continue
            fn = normalize_match_key(folder.name)
            if fn != nk and nk not in fn and fn not in nk:
                continue
            blob = folder.name + " " + folder.as_posix()
            pd = parse_date_from_path_string(blob)
            if pd:
                found.append(pd)
    return found


def find_backup_conversation_note(display: str, vox_dir: Path) -> Path | None:
    """Prefer an older backup copy that still has pre-migration filesystem dates."""
    nk = normalize_match_key(display)
    paths: list[Path] = []
    for b in sorted(vox_dir.glob("migration_backup_*")):
        conv = b / "Conversations"
        if not conv.is_dir():
            continue
        exact = conv / f"{display}.md"
        if exact.is_file():
            paths.append(exact)
            continue
        if nk:
            for c in conv.glob("*.md"):
                if normalize_match_key(c.stem) == nk:
                    paths.append(c)
                    break
    seen: set[Path] = set()
    uniq = []
    for c in paths:
        rp = c.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(c)
    paths = uniq
    for c in paths:
        bd, _ = file_artifact_dates(c)
        if not is_suspect_migration_day(bd):
            return c
    return paths[0] if paths else None


def find_docx_backup_matches(display: str, docx_backup: Path) -> list[Path]:
    if not docx_backup.is_dir():
        return []
    nk = normalize_match_key(display)
    hits: list[Path] = []
    for p in docx_backup.glob("*.docx"):
        if normalize_match_key(p.stem).find(nk) >= 0 or nk in normalize_match_key(
            p.name
        ):
            hits.append(p)
    return hits


def find_voice_audio_for_slug_fragment(slug_fragment: str, voice_archive: Path) -> list[Path]:
    if not voice_archive.is_dir():
        return []
    frag = slug_fragment.lower()
    out: list[Path] = []
    for p in voice_archive.rglob("*.m4a"):
        if frag in p.name.lower():
            out.append(p)
    return out


def strip_yaml_frontmatter(text: str) -> str:
    """Remove leading --- ... --- so we don't parse `date:` from the note itself as call date."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")


def strip_transcript_embeds(text: str) -> str:
    """Remove Transcript wikilinks so ISO in filenames isn't treated as call date."""
    return re.sub(r"!?\[\[Transcripts/[^\]]+\]\]", " ", text)


def infer_fallback_conversation_date(
    *,
    display: str,
    note_path: Path | None,
    transcript_path: Path | None,
    pipeline_roots: list[tuple[str, Path]],
    docx_backup: Path,
    voice_archive: Path,
    vox_dir: Path,
    text_hint: str = "",
) -> date:
    """
    Tiered inference so we don't pick min(2025 call, 2023 typo) from unrelated blobs.
    Order: pipeline path dates → text (ISO / English / MDY) → old backup note stat →
    docx → pipeline media stats → archived audio → current files → today.
    """
    now = date.today()
    window_end = now + timedelta(days=7)

    def in_window(d: date) -> bool:
        return date(2018, 1, 1) <= d <= window_end

    blob_parts: list[str] = []
    if transcript_path and transcript_path.is_file():
        try:
            blob_parts.append(
                transcript_path.read_text(encoding="utf-8", errors="replace")[:12000]
            )
        except OSError:
            pass
    if text_hint:
        cleaned = strip_transcript_embeds(strip_yaml_frontmatter(text_hint))
        blob_parts.append(cleaned[:12000])
    blobs_joined = "\n".join(blob_parts)

    # A) Dates in pipeline folder / path names (strong)
    pfd = [
        d
        for d in pipeline_folder_dates_for_display(display, pipeline_roots)
        if in_window(d)
    ]
    if pfd:
        return min(pfd)

    # B) Explicit dates in transcript or note body
    text_ds = [d for d in dates_from_text_blob(blobs_joined) if in_window(d)]
    if text_ds:
        return min(text_ds)

    # C) ~/.vox backup (oldest copy with non-suspect birth preferred by finder)
    bu = find_backup_conversation_note(display, vox_dir)
    if bu:
        bd, md = file_artifact_dates(bu)
        for d in (bd, md):
            if in_window(d) and not is_suspect_migration_day(d):
                return d
        if in_window(bd):
            return bd

    # D) docx_backup timestamps
    for dx in find_docx_backup_matches(display, docx_backup):
        bdx = best_date_from_stats([dx], prefer_not_suspect=True)
        if bdx and in_window(bdx) and not is_suspect_migration_day(bdx):
            return bdx

    # E) Pipeline media files
    pm = find_pipeline_media_for_display(display, pipeline_roots)
    bpm = best_date_from_stats(pm, prefer_not_suspect=True)
    if bpm and in_window(bpm):
        return bpm

    # F) Archived audio matching transcript slug
    if transcript_path and transcript_path.name:
        sp = split_dated_transcript_filename(transcript_path.name)
        if sp:
            _, slug = sp
            aud = find_voice_audio_for_slug_fragment(slug.replace("-", ""), voice_archive)
            if not aud:
                aud = find_voice_audio_for_slug_fragment(slug[:16], voice_archive)
            ba = best_date_from_stats(aud, prefer_not_suspect=True)
            if ba and in_window(ba):
                return ba

    # G) Current transcript / note
    for p in (transcript_path, note_path):
        if p and p.is_file():
            b = best_date_from_stats([p], prefer_not_suspect=True)
            if b and in_window(b):
                return b

    if note_path and note_path.is_file():
        _, md = file_artifact_dates(note_path)
        return md
    return date.today()


def default_pipeline_roots() -> list[tuple[str, Path]]:
    h = Path.home()
    return [
        ("robox", h / "studio-kensense" / "robox" / "Calls" / "results"),
        ("studio", h / "studio-kensense" / "transcription" / "results"),
        ("sonnet", h / "studio-kensense" / "sonnet" / "transcription" / "results"),
    ]


def infer_date_smart(
    text: str,
    path: Path | None = None,
    *,
    transcript_path: Path | None = None,
    display_for_pipeline: str | None = None,
    pipeline_roots: list[tuple[str, Path]] | None = None,
    docx_backup: Path | None = None,
    voice_archive: Path | None = None,
    vox_dir: Path | None = None,
) -> date:
    """
    Primary: YYYY-MM-DD / M-D-YY in `text`.
    Fallback: transcript + pipeline + backups + filesystem stats (see infer_fallback_conversation_date).
    """
    d = parse_ymd(text)
    if d:
        return d
    d = parse_last_mdy(text)
    if d:
        return d
    disp = display_for_pipeline or text
    roots = pipeline_roots if pipeline_roots is not None else default_pipeline_roots()
    home = Path.home()
    return infer_fallback_conversation_date(
        display=disp,
        note_path=path,
        transcript_path=transcript_path,
        pipeline_roots=roots,
        docx_backup=docx_backup or (home / "Voice" / "archive" / "docx_backup"),
        voice_archive=voice_archive or (home / "Voice" / "archive"),
        vox_dir=vox_dir or (home / ".vox"),
        text_hint=text,
    )
