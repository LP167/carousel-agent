"""ask_human — stop and ask for a fact or decision the sources cannot provide."""
SPEC = {"name": "ask_human",
        "description": "Ask the human for a fact or decision the sources cannot provide. Stops the run until answered. Do not use for things you can read.",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["question"],
                       "properties": {"question": {"type": "string"}}}}


def run(args, ctx):
    rec = ctx.record
    unread = [sid for sid, s in rec.sources.items() if not s.get("read")]
    if unread:
        return False, f"read all sources before asking a human: {', '.join(unread)}"
    rec.status, rec.question = "needs_input", args["question"]
    return True, "question sent to the human; the run pauses"
