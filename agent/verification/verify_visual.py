"""Visual check (Muse Spark image input): the model looks at the rendered PNGs —
pixels, not the HTML — and reports what a reader would actually see wrong."""
from __future__ import annotations

from meta import spark
from render.render import preview

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["slides"],
          "properties": {"slides": {"type": "array", "items": {
              "type": "object", "additionalProperties": False, "required": ["slide_id", "issues"],
              "properties": {"slide_id": {"type": "string"}, "issues": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False, "required": ["kind", "severity", "note"],
                  "properties": {"kind": {"type": "string", "enum": ["clipped", "unreadable", "mismatch", "overlap", "bad_cutout", "off_brand"]},
                                 "severity": {"type": "string", "enum": ["block", "warn"]},
                                 "note": {"type": "string"}}}}}}}}}

SYSTEM = (
    "You are the final visual QA for an Instagram carousel (4:5). Each image is labelled with its slide id and the exact "
    "text that SHOULD appear. Look at the pixels. Report: clipped (text or subject cut off at an edge or mid-sentence), "
    "unreadable (text hard to read against what is behind it), mismatch (visible text differs from the expected text — "
    "missing words, wrong numbers), overlap (elements collide), bad_cutout (product cutout has missing parts, halo, or "
    "background left in), off_brand (looks broken or unprofessional). Use severity block only for problems a reader would "
    "notice; warn for minor ones. An empty issues list means the slide is fine."
)


def check(t, record, report: list[dict], qa_size) -> list[dict]:
    parts = []
    for r in report:
        s = record.slide(r["id"])
        expected = " / ".join([s["title"]] + [c["text"] for c in record.claims_for(r["id"])])
        parts.append(spark.text_part(f"SLIDE {r['id']} ({s['type']}). Expected text: {expected}"))
        parts.append(spark.image_part(preview(r["png"], tuple(qa_size))))
    d = spark.ask_json(t, SYSTEM, parts, SCHEMA, "visual_check", "verify_visual")
    out = []
    for s in d["slides"]:
        for i in s["issues"]:
            if i["severity"] == "block":
                out.append({"slide_id": s["slide_id"], **i})
    return out
