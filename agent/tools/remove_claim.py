"""remove_claim — take a sentence off its slide."""
SPEC = {
    "name": "remove_claim",
    "description": "Remove one sentence by claim id (e.g. to shorten an overflowing slide).",
    "parameters": {"type": "object", "additionalProperties": False, "required": ["claim_id"],
                   "properties": {"claim_id": {"type": "string"}}},
}


def run(args, ctx):
    rec = ctx.record
    before = len(rec.claims)
    rec.claims = [c for c in rec.claims if c["id"] != args["claim_id"]]
    if len(rec.claims) == before:
        return False, f"no claim '{args['claim_id']}'"
    if rec.render:
        rec.render["stale"] = True
    return True, f"removed {args['claim_id']}"
