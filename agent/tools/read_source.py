"""read_source — open one source. Audio is transcribed by Muse Voice Transcribe on first read."""
from meta import transcribe

SPEC = {
    "name": "read_source",
    "description": "Read one source by id. Returns its text with page numbers you must use in quotes. Photos return a description of how to use them.",
    "parameters": {"type": "object", "additionalProperties": False, "required": ["source_id"],
                   "properties": {"source_id": {"type": "string"}}},
}


def run(args, ctx):
    rec = ctx.record
    src = rec.sources.get(args["source_id"])
    if not src:
        return False, f"no source '{args['source_id']}'. Valid ids: {', '.join(rec.sources)}"
    if src["kind"] == "photo":
        src["read"] = True
        return True, (f"'{args['source_id']}' is a product photo. It has no text to quote. Use it with "
                      f"request_visual(kind='cutout', source_id='{args['source_id']}', prompt='<object to cut out>') on a visual slide.")
    if src["kind"] == "audio" and not src["pages"]:
        # bias recognition toward names that appear in the brand's own documents
        import re
        docs = " ".join(p for s in rec.sources.values() for p in (s.get("pages") or []))
        names = sorted(set(re.findall(r"(?<=[a-z,] )[A-Z][a-zA-Z-]{2,}", docs)))
        text = transcribe.transcribe(ctx.t, src["path"], keywords=[rec.brand.get("name", "")] + names)
        src["pages"] = [text.strip()]
    src["read"] = True
    body = "\n\n".join(f"--- page {i+1} ---\n{p}" for i, p in enumerate(src["pages"]))
    return True, f"{args['source_id']} ({src['kind']}, '{src['title']}'):\n{body}"
