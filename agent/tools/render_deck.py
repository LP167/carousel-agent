"""render_deck — HTML → PNG for every slide, with code render checks inside."""
from pathlib import Path

from render.render import render_slides

SPEC = {"name": "render_deck",
        "description": "Render all slides to 1080x1350 PNG and run layout checks (overflow, font size, contrast, margins, footer).",
        "parameters": {"type": "object", "additionalProperties": False, "required": [], "properties": {}}}


def footer_for(rec, slide_id):
    for c in rec.claims_for(slide_id):
        for q in c.get("quotes", []):
            src = rec.sources[q["source_id"]]
            return f"Source: {src['title']} · p.{q['page']}"
    return ""


def build_slides(rec):
    slides = []
    for s in rec.outline:
        a = rec.assets.get(s["id"], {})
        slides.append({"id": s["id"], "type": s["type"], "title": s["title"], "kicker": s.get("kicker", ""),
                       "lines": [c["text"] for c in rec.claims_for(s["id"])], "footer": footer_for(rec, s["id"]),
                       "background": a.get("background"), "cutout": a.get("cutout")})
    return slides


def run(args, ctx):
    rec = ctx.record
    if not rec.outline:
        return False, "no outline yet"
    empty = [s["id"] for s in rec.outline if not rec.claims_for(s["id"])]
    if empty:
        return False, f"these slides have no sentences yet: {', '.join(empty)}"
    rec.counters["render_version"] += 1
    v = rec.counters["render_version"]
    report = render_slides(build_slides(rec), rec.brand, Path(ctx.run_dir) / "render" / f"v{v}")
    ok = all(not r["problems"] for r in report)
    rec.render = {"ok": ok, "version": v, "report": report, "stale": False}
    if ok:
        return True, f"render v{v}: all {len(report)} slides pass layout checks"
    lines = [f"{r['id']}: " + "; ".join(r["problems"]) for r in report if r["problems"]]
    return False, f"render v{v} has layout problems — fix and render again:\n" + "\n".join(lines)
