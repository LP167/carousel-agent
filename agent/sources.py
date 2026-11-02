"""Loads a sample folder into source entries. Text is extracted locally so the
citation gate can check quotes character-for-character; audio is transcribed by
Muse Voice Transcribe when the agent first reads it."""
from __future__ import annotations

import re
from pathlib import Path

TEXT_EXT = {".md", ".txt"}
AUDIO_EXT = {".wav", ".m4a", ".mp3", ".aiff", ".aif"}
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _pdf_pages(path: Path) -> list[str]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return [(p.extract_text() or "").strip() for p in pdf.pages]


def _md_pages(path: Path) -> list[str]:
    """Markdown/text: one 'page' per blank-line-separated section of ~1200 chars."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", path.read_text()) if p.strip()]
    pages, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > 1200:
            pages.append(cur)
            cur = ""
        cur = (cur + "\n\n" + p).strip()
    if cur:
        pages.append(cur)
    return pages


def discover(sample_dir: Path) -> tuple[str, dict, dict]:
    """Returns (objective, brand, sources). objective.md and brand.json are config, not sources."""
    import json

    sample_dir = Path(sample_dir)
    objective = (sample_dir / "objective.md").read_text().strip()
    brand = json.loads((sample_dir / "brand.json").read_text()) if (sample_dir / "brand.json").exists() else {}
    sources = {}
    for f in sorted(sample_dir.iterdir()):
        if f.name in ("objective.md", "brand.json") or f.name.startswith("."):
            continue
        ext = f.suffix.lower()
        sid = re.sub(r"[^a-z0-9_]+", "_", f.stem.lower())
        if ext == ".pdf":
            sources[sid] = {"kind": "pdf", "path": str(f), "title": f.stem, "pages": _pdf_pages(f)}
        elif ext in TEXT_EXT:
            sources[sid] = {"kind": "text", "path": str(f), "title": f.stem, "pages": _md_pages(f)}
        elif ext in AUDIO_EXT:
            sources[sid] = {"kind": "audio", "path": str(f), "title": "voice brief", "pages": []}
        elif ext in PHOTO_EXT:
            sources[sid] = {"kind": "photo", "path": str(f), "title": f.stem, "pages": []}
    for s in sources.values():  # friendlier footer titles: first line of a document
        if s["kind"] in ("pdf", "text") and s["pages"]:
            first = s["pages"][0].strip().splitlines()[0].lstrip("# ").strip()
            if 3 <= len(first) <= 60:
                s["title"] = first
    return objective, brand, sources
