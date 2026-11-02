"""Outline coverage. A hidden key-point list is built by a separate Spark call the
agent never sees; Spark then judges which key points the outline covers and code
computes the score. Feedback names only the *kind* of thing missing."""
from __future__ import annotations

import json
from pathlib import Path

from meta import spark

KP_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["keypoints"],
             "properties": {"keypoints": {"type": "array", "items": {
                 "type": "object", "additionalProperties": False, "required": ["point", "category"],
                 "properties": {"point": {"type": "string"},
                                "category": {"type": "string", "enum": ["benefit", "spec", "proof", "price_or_terms", "audience", "story", "other"]}}}}}}

COV_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["coverage"],
              "properties": {"coverage": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False, "required": ["index", "covered_by"],
                  "properties": {"index": {"type": "integer"}, "covered_by": {"type": "string"}}}}}}


def build_keypoints(t, record, run_dir: Path) -> list:
    path = Path(run_dir) / "hidden" / "keypoints.json"
    if path.exists():
        return json.loads(path.read_text())
    text = "\n\n".join(f"[{sid} p.{i+1}]\n{p}" for sid, s in record.sources.items() for i, p in enumerate(s.get("pages") or []))
    d = spark.ask_json(
        t,
        "You are an editor. From the source material, list the 5-8 points a marketing carousel about it must not leave out. "
        "Only points actually stated in the sources.",
        [spark.text_part(f"Objective: {record.objective}\n\nSources:\n{text[:60000]}")],
        KP_SCHEMA, "keypoints", "verify_outline_keypoints")
    kps = d["keypoints"][:8]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kps, ensure_ascii=False, indent=1))
    return kps


def check(t, record, run_dir: Path, slides: list) -> tuple[bool, str, float]:
    kps = build_keypoints(t, record, run_dir)
    outline = "\n".join(f"{s['id']} [{s['type']}] {s['title']}" for s in slides)
    listing = "\n".join(f"{i}. {k['point']}" for i, k in enumerate(kps))
    d = spark.ask_json(
        t,
        "For each numbered key point, say which slide id covers it, or 'none'. A slide covers a point only if its title clearly addresses it.",
        [spark.text_part(f"Key points:\n{listing}\n\nOutline:\n{outline}")],
        COV_SCHEMA, "coverage", "verify_outline_coverage")
    ids = {s["id"] for s in slides}
    covered = {c["index"] for c in d["coverage"] if c["covered_by"] in ids}
    score = len(covered) / max(1, len(kps))
    types = [s["type"] for s in slides]
    shape_ok = types.count("cover") == 1 and types.count("cta") == 1 and sum(x in ("point", "quote", "visual") for x in types) >= 5 \
        and 7 <= len(slides) <= 9 and types[0] == "cover" and types[-1] == "cta"
    if score >= 0.7 and shape_ok:
        return True, f"outline accepted (coverage {score:.0%})", score
    problems = []
    if not shape_ok:
        problems.append("shape: 7-9 slides, first is the only cover, last is the only cta, at least 5 point/quote/visual slides")
    if score < 0.7:
        missing_cats = sorted({kps[i]["category"] for i in range(len(kps)) if i not in covered})
        problems.append("the outline leaves out important material of these kinds: " + ", ".join(missing_cats).replace("_", " "))
    return False, "outline rejected — " + "; ".join(problems), score
