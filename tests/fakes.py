"""Scripted stand-in for the Meta API so the agent's logic can be tested offline."""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from meta.client import Transport

FIX = Path(__file__).parent / "fixtures"


def photo() -> Path:
    """A synthetic 'product photo': a green rounded bottle on beige. Drawn in code, no rights issues."""
    from PIL import Image, ImageDraw

    FIX.mkdir(exist_ok=True)
    p = FIX / "bottle.png"
    if not p.exists():
        im = Image.new("RGB", (800, 1000), "#E9E0D2")
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((300, 180, 500, 860), 60, fill="#7FA08C")
        d.rounded_rectangle((330, 120, 470, 200), 20, fill="#2F3A33")
        im.save(p)
    return p


def sam_text() -> str:
    from meta_sam_parser._mask_codec import _encode_raster

    W, H = 50, 185  # box-local mask raster for box (300,120)-(500,860)
    r = [1 if 0 <= x < W else 0 for y in range(H) for x in range(W)]
    return f"<0f>0<|box;x1=300;y1=120;x2=499;y2=859;w=800;h=1000|><|mask;x=0;y=0;data={H},{W},{_encode_raster(r, W, H)}|>"


def png_b64(color="#C9D8CC") -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1024, 1280), color).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def tool(name, **args):
    return {"content": "", "tool_calls": [{"id": "x", "type": "function",
                                           "function": {"name": name, "arguments": json.dumps(args)}}]}


def js(obj):
    return {"content": json.dumps(obj), "tool_calls": []}


class FakeTransport(Transport):
    def __init__(self, script: dict, record_to: Path | None = None, **kw):
        super().__init__("live", **kw)
        self.record_to = record_to
        self.script = {k: list(v) for k, v in script.items()}
        self.seen = []

    def call(self, kind, fn, payload_summary=None):
        self.n += 1
        self.seen.append(kind)
        q = self.script.get(kind)
        if not q:
            raise AssertionError(f"unscripted call #{self.n}: {kind}")
        resp = q.pop(0)
        if self.record_to:
            (self.record_to / "calls").mkdir(parents=True, exist_ok=True)
            (self.record_to / "calls" / f"{self.n:04d}_{kind}.json").write_text(json.dumps({"kind": kind, "response": resp}))
        return resp
