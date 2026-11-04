"""Citation gate (pure code). A quote must appear, after normalisation, on the page it cites."""
from __future__ import annotations

import re
import unicodedata

NUMERIC = re.compile(r"\d|%|원|\$|€|£")


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" .,;:!?\"'()[]")
    return s.lower()


def check_quote(quote: dict, sources: dict, min_chars: int) -> str | None:
    """Returns None if OK, else a refusal the model can act on."""
    sid, page, text = quote.get("source_id"), quote.get("page"), quote.get("quote", "")
    src = sources.get(sid)
    if not src:
        return f"source '{sid}' does not exist. Valid ids: {', '.join(sources)}"
    pages = src.get("pages") or []
    if not pages:
        return f"source '{sid}' has no readable text (read it first, or it is a photo)"
    if not isinstance(page, int) or not 1 <= page <= len(pages):
        return f"page {page} is out of range for '{sid}' (1–{len(pages)})"
    q = normalize(text)
    if len(q) < min_chars:
        return f"quote is {len(q)} characters; quote at least {min_chars} characters of the original wording"
    if q not in normalize(pages[page - 1]):
        others = [i + 1 for i, p in enumerate(pages) if q in normalize(p)]
        hint = f" It does appear on page {others[0]}." if others else " Copy the wording exactly from the page; do not paraphrase inside a quote."
        return f"that quote is not on {sid} page {page}.{hint}"
    return None


def needs_quote(slide_type: str, text: str) -> bool:
    """Cover / CTA lines are framing and may go unquoted unless they carry numbers or money."""
    if slide_type in ("cover", "cta"):
        return bool(NUMERIC.search(text))
    return True


NUMBER = re.compile(r"\d+(?:[.,/]\d+)*")


def number_gaps(text: str, quotes: list) -> list[str]:
    """Numbers in the sentence that no quote contains. Checked in code so an invented figure cannot slip through."""
    quoted = normalize(" ".join(q.get("quote", "") for q in quotes)).replace(",", "")
    return [n for n in dict.fromkeys(NUMBER.findall(text)) if n.replace(",", "") not in quoted]
