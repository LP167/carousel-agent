"""record_claim — one on-slide sentence plus the exact source wording behind it. Citation gate runs inside."""
from agent.verification.citation import check_quote, needs_quote, number_gaps

SPEC = {
    "name": "record_claim",
    "description": ("Put one sentence on a slide. Every factual sentence needs at least one quote copied word-for-word from a "
                    "source page (min 15 characters). Use replaces=<claim id> to rewrite an existing sentence. "
                    "Keep sentences short: point slides take 2-3 sentences, ~60 characters each."),
    "parameters": {"type": "object", "additionalProperties": False, "required": ["slide_id", "text", "quotes", "replaces"],
                   "properties": {
                       "slide_id": {"type": "string"},
                       "text": {"type": "string"},
                       "replaces": {"type": "string", "description": "claim id to replace, or empty string"},
                       "quotes": {"type": "array", "items": {
                           "type": "object", "additionalProperties": False, "required": ["source_id", "page", "quote"],
                           "properties": {"source_id": {"type": "string"}, "page": {"type": "integer"}, "quote": {"type": "string"}}}}}},
}


def run(args, ctx):
    rec = ctx.record
    slide = rec.slide(args["slide_id"])
    if not slide:
        return False, f"no slide '{args['slide_id']}'. Call set_outline first or use a valid id."
    quotes = args.get("quotes") or []
    if not quotes and needs_quote(slide["type"], args["text"]):
        return False, "this sentence states a fact but has no quote. Add the exact source wording that supports it."
    for q in quotes:
        err = check_quote(q, rec.sources, ctx.cfg["citation"]["min_quote_chars"])
        if err:
            return False, "citation refused: " + err
    nums = number_gaps(args["text"], quotes)
    if nums:
        return False, (f"citation refused: the sentence uses {', '.join(nums)} but none of its quotes contain "
                       f"{'it' if len(nums) == 1 else 'them'}. Quote the source wording that states the number, or remove it.")
    rep = (args.get("replaces") or "").strip()
    if rep:
        old = next((c for c in rec.claims if c["id"] == rep), None)
        if not old:
            return False, f"no claim '{rep}' to replace"
        old.update(text=args["text"], quotes=quotes, slide_id=args["slide_id"])
        cid = rep
    else:
        rec.counters["claim_seq"] += 1
        cid = f"c{rec.counters['claim_seq']}"
        rec.claims.append({"id": cid, "slide_id": args["slide_id"], "text": args["text"], "quotes": quotes})
    if rec.render:
        rec.render["stale"] = True
    return True, f"recorded {cid} on {args['slide_id']}" + (" (replaced)" if rep else "")
