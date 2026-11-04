"""Deck rules (pure code), first gate inside submit_deck."""
from __future__ import annotations

import re
from pathlib import Path

NUM = re.compile(r"\d+(?:[.,]\d+)?")


def check(record) -> list[str]:
    problems = []
    if not record.outline:
        return ["no outline"]
    for s in record.outline:
        cs = record.claims_for(s["id"])
        if not cs:
            problems.append(f"{s['id']} has no sentences")
        elif s["type"] == "point" and len(cs) < 2:
            problems.append(f"{s['id']} is a point slide with only one sentence; add a second supporting sentence (point slides carry 2-3)")
        if s["type"] == "quote" and cs and not cs[0].get("quotes"):
            problems.append(f"{s['id']} is a quote slide but its first sentence has no source quote")
        if s["type"] == "visual" and not record.assets.get(s["id"], {}).get("cutout"):
            problems.append(f"{s['id']} is a visual slide without a cutout (request_visual kind=cutout)")
        # numbers in a headline must be backed by a quote on the same slide
        quoted = " ".join(q["quote"] for c in cs for q in c.get("quotes", []))
        for n in NUM.findall(s["title"]):
            if n not in quoted:
                problems.append(f"{s['id']} title uses the number {n} but no quote on that slide contains it")
    for sid, a in record.assets.items():
        for kind, p in a.items():
            if not Path(p).exists():
                problems.append(f"{sid} {kind} file missing")
    if record.status == "needs_input":
        problems.append("an ask_human question is still open")
    r = record.render
    if not r or not r.get("ok") or r.get("stale"):
        problems.append("the deck must be rendered (render_deck) and pass render checks after the last change")
    return problems
