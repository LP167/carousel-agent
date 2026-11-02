"""Claim check (Muse Spark, structured output): does each quote actually support its sentence?"""
from __future__ import annotations

from meta import spark

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["results"],
          "properties": {"results": {"type": "array", "items": {
              "type": "object", "additionalProperties": False, "required": ["claim_id", "verdict", "reason"],
              "properties": {"claim_id": {"type": "string"},
                             "verdict": {"type": "string", "enum": ["supported", "overstated", "unsupported"]},
                             "reason": {"type": "string"}}}}}}

SYSTEM = (
    "You audit marketing copy against its cited evidence. For each sentence, read ONLY its quotes. "
    "supported: every factual statement in the sentence is said by the quotes (rewording is fine). "
    "overstated: the sentence says more than the quotes — a bigger or rounded-up number, a wider scope "
    "('all', 'always', 'best'), a cause the quotes do not state, or a guarantee. "
    "unsupported: the quotes do not address the sentence's claim. "
    "Sentences without quotes are framing lines; mark them supported unless they assert a fact. Give a one-line reason."
)


def check(t, record) -> list[dict]:
    items = []
    for c in record.claims:
        qs = " | ".join(f"\"{q['quote']}\" ({q['source_id']} p.{q['page']})" for q in c.get("quotes", [])) or "(no quotes)"
        items.append(f"{c['id']}: SENTENCE: {c['text']}\n    QUOTES: {qs}")
    d = spark.ask_json(t, SYSTEM, [spark.text_part("\n".join(items))], SCHEMA, "claim_check", "verify_claims")
    return [r for r in d["results"] if r["verdict"] != "supported"]
