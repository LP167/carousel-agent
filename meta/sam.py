"""SAM 3.1 — cuts a product / subject out of the user's own photo.

Text prompt + image go to /v1/responses (streamed). The output text uses SAM's
box/mask grammar, which we parse with Meta's official `meta-sam-parser`.
The mask raster is box-local, so we resize it onto the box and build an RGBA
cutout of the original photo.
"""
from __future__ import annotations

from pathlib import Path

from .client import Transport, image_data_url


def _stream_text(t: Transport, image_path: Path, prompt: str) -> str:
    model = t.cfg["models"]["segment"]
    data_url = image_data_url(image_path, max_side=1600)

    def live():
        parts = []
        with t.openai.responses.stream(
            model=model,
            input=[{
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }],
        ) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    parts.append(event.delta)
        return {"text": "".join(parts)}

    return t.call("sam", live, {"model": model, "prompt": prompt, "image": Path(image_path).name})["text"]


def parse(text: str):
    """Returns list of (box(l,t,r,b), mask_record) for each object found."""
    from meta_sam_parser import CompletedOutcome, SegmentationBoxRecord, SegmentationMaskRecord, image_segmentation_format

    parser = image_segmentation_format().create_parser()
    parser.push(text if text.endswith("\n") else text + "\n", emit=False)
    result = parser.finish(CompletedOutcome()).result
    boxes, masks = {}, {}
    for rec in result.records:
        if isinstance(rec, SegmentationBoxRecord):
            boxes[rec.object_id] = (rec.left, rec.top, rec.right, rec.bottom)
        elif isinstance(rec, SegmentationMaskRecord):
            masks[rec.object_id] = rec
    return [(boxes.get(k), masks[k]) for k in masks], list(result.diagnostics)


def cutout(t: Transport, image_path: Path, prompt: str, out_path: Path) -> dict:
    """Largest matching object → transparent PNG cropped to its box."""
    from meta_sam_parser import decode_mask_to_raster
    from PIL import Image

    text = _stream_text(t, Path(image_path), prompt)
    objects, diags = parse(text)
    if not objects:
        return {"ok": False, "reason": f"SAM found no '{prompt}'", "diagnostics": [str(d) for d in diags][:3]}

    src = Image.open(image_path).convert("RGBA")
    src.thumbnail((1600, 1600))  # same scale we sent

    def area(o):
        b = o[1].bounds
        return (b.right - b.left) * (b.bottom - b.top)

    _, rec = max(objects, key=area)
    m, b = rec.mask, rec.bounds
    raster = decode_mask_to_raster(m)
    mask_img = Image.frombytes("L", (m.width, m.height), bytes(v * 255 for v in raster))
    l, tp, r, bt = (int(round(v)) for v in (b.left, b.top, b.right, b.bottom))
    l, tp = max(l, 0), max(tp, 0)
    r, bt = min(r, src.width), min(bt, src.height)
    if r - l < 8 or bt - tp < 8:
        return {"ok": False, "reason": "mask box too small"}
    mask_img = mask_img.resize((r - l, bt - tp), Image.BILINEAR)
    crop = src.crop((l, tp, r, bt))
    crop.putalpha(mask_img)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out_path)
    coverage = sum(1 for v in raster if v) / max(1, len(raster))
    return {"ok": True, "path": str(out_path), "size": [crop.width, crop.height],
            "objects_found": len(objects), "mask_coverage": round(coverage, 3)}
