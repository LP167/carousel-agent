"""submit_deck — final gate: rules (code) → claim check (Spark) → visual check (Spark looks at the PNGs)."""
from agent.verification import verify_claims, verify_rules, verify_visual

SPEC = {"name": "submit_deck",
        "description": "Submit the rendered deck for final checks. If every check passes it goes to a human for sign-off.",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["summary"],
                       "properties": {"summary": {"type": "string", "description": "one line for the reviewer"}}}}


def _reject(ctx, stage, lines):
    rec = ctx.record
    rec.counters["submit_rejects"] += 1
    n, cap = rec.counters["submit_rejects"], ctx.cfg["agent"]["max_submit_rejects"]
    if n >= cap:
        rec.status = "needs_review"
        rec.flags.append(f"stopped after {n} rejected submissions (last: {stage})")
    return False, f"submission rejected by {stage} ({n}/{cap}):\n" + "\n".join(lines)


def run(args, ctx):
    rec = ctx.record
    probs = verify_rules.check(rec)
    if probs:
        return _reject(ctx, "rule check", probs)
    bad = verify_claims.check(ctx.t, rec)
    if bad:
        return _reject(ctx, "claim check (Muse Spark)", [f"{b['claim_id']} {b['verdict']}: {b['reason']}" for b in bad])
    vis = verify_visual.check(ctx.t, rec, rec.render["report"], ctx.cfg["render"]["qa_preview"])
    if vis:
        rec.render["stale"] = True
        return _reject(ctx, "visual check (Muse Spark looked at the PNGs)", [f"{v['slide_id']} {v['kind']}: {v['note']}" for v in vis])
    rec.status = "awaiting_signoff"
    rec.flags.append("summary: " + args["summary"])
    return True, "all checks passed — waiting for human sign-off"
