"""request_visual — SAM 3.1 cutout from the user's photo, or Muse Image cover/background."""
from pathlib import Path

from meta import image, sam

SPEC = {
    "name": "request_visual",
    "description": ("Create an image for a slide. kind='cutout': SAM 3.1 cuts the named object out of a product photo "
                    "(source_id = a photo source, prompt = the object, e.g. 'water bottle'). kind='background': Muse Image "
                    "generates a background (prompt = scene or texture only — never a product, the product comes from the cutout). Cover slides should get a background."),
    "parameters": {"type": "object", "additionalProperties": False, "required": ["slide_id", "kind", "prompt", "source_id"],
                   "properties": {"slide_id": {"type": "string"},
                                  "kind": {"type": "string", "enum": ["cutout", "background"]},
                                  "prompt": {"type": "string"},
                                  "source_id": {"type": "string", "description": "photo source id for cutout, empty for background"}}},
}


def run(args, ctx):
    rec = ctx.record
    slide = rec.slide(args["slide_id"])
    if not slide:
        return False, f"no slide '{args['slide_id']}'"
    out_dir = Path(ctx.run_dir) / "assets"
    if args["kind"] == "cutout":
        src = rec.sources.get(args["source_id"])
        if not src or src["kind"] != "photo":
            photos = [k for k, v in rec.sources.items() if v["kind"] == "photo"]
            return False, f"cutout needs a photo source. Photos: {', '.join(photos) or 'none'}"
        r = sam.cutout(ctx.t, Path(src["path"]), args["prompt"], out_dir / f"{args['slide_id']}_cutout.png")
        if not r.get("ok"):
            return False, f"SAM could not cut out '{args['prompt']}': {r.get('reason')}. Try a simpler object name."
        if r["size"][0] < 200 or r["size"][1] < 200:
            return False, f"cutout is only {r['size']} px — too small to use. Try another photo or object."
        rec.assets.setdefault(args["slide_id"], {})["cutout"] = r["path"]
        msg = f"cutout saved ({r['size'][0]}x{r['size'][1]}, {r['objects_found']} match(es), mask covers {r['mask_coverage']:.0%} of its box)"
    else:
        b = rec.brand
        prompt = (f"{args['prompt']}. Background only: surfaces, light and texture. Calm, uncluttered composition with empty "
                  f"space in the lower half for a text panel. Palette close to {b.get('bg', '')} and {b.get('accent', '')}. "
                  f"Do not show any bottle, cup, tumbler, container or other product (the real product appears elsewhere). "
                  f"No text, no letters, no logos, no watermark.")
        p = image.generate(ctx.t, prompt, out_dir / f"{args['slide_id']}_background.png")
        from PIL import Image
        if min(Image.open(p).size) < 512:
            return False, "generated image is smaller than 512px; try again"
        rec.assets.setdefault(args["slide_id"], {})["background"] = str(p)
        msg = "background generated"
    if rec.render:
        rec.render["stale"] = True
    return True, msg + f" for {args['slide_id']}"
