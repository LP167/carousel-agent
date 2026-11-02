"""set_outline — save the slide plan. verify_outline runs inside; the agent cannot skip it."""
from agent.verification import verify_outline

SPEC = {
    "name": "set_outline",
    "description": ("Save the carousel plan: 7-9 slides, first type 'cover', last type 'cta', the rest point/quote/visual. "
                    "Titles are short headlines (max ~40 characters). Replaces any previous outline and its sentences."),
    "parameters": {"type": "object", "additionalProperties": False, "required": ["slides"],
                   "properties": {"slides": {"type": "array", "items": {
                       "type": "object", "additionalProperties": False, "required": ["type", "title", "kicker"],
                       "properties": {"type": {"type": "string", "enum": ["cover", "point", "quote", "visual", "cta"]},
                                      "title": {"type": "string"},
                                      "kicker": {"type": "string", "description": "2-3 word label above the title"}}}}}},
}


def run(args, ctx):
    rec = ctx.record
    unread = [sid for sid, s in rec.sources.items() if not s.get("read")]
    if unread:
        return False, f"read every source before planning. Not read yet: {', '.join(unread)}"
    slides = [{"id": f"s{i+1}", **s} for i, s in enumerate(args["slides"])]
    ok, msg, score = verify_outline.check(ctx.t, rec, ctx.run_dir, slides)
    if not ok:
        rec.counters["outline_rejects"] += 1
        if rec.counters["outline_rejects"] < ctx.cfg["agent"]["max_outline_rejects"]:
            return False, msg + f" (attempt {rec.counters['outline_rejects']} of {ctx.cfg['agent']['max_outline_rejects']})"
        rec.flags.append(f"outline accepted after {rec.counters['outline_rejects']} rejections, coverage {score:.0%}")
        msg = f"outline accepted with a flag for the reviewer (coverage {score:.0%})"
    rec.outline, rec.claims, rec.assets = slides, [], {}
    rec.outline_score = score
    rec.render = {}
    return True, msg + ". Slide ids: " + ", ".join(f"{s['id']}={s['type']}" for s in slides)
