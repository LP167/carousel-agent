"""Muse Image 1.0 — covers and backgrounds."""
from __future__ import annotations

import base64
from pathlib import Path

from .client import Transport


def generate(t: Transport, prompt: str, out_path: Path) -> Path:
    model = t.cfg["models"]["image"]

    def live():
        r = t.openai.images.generate(model=model, prompt=prompt, n=1)
        d = r.model_dump()
        item = d["data"][0]
        if item.get("b64_json"):
            return {"b64": item["b64_json"]}
        if item.get("url"):
            import httpx

            data = httpx.get(item["url"], timeout=60).content
            return {"b64": base64.b64encode(data).decode()}
        raise RuntimeError(f"unexpected image response keys: {list(item)}")

    resp = t.call("image", live, {"model": model, "prompt": prompt})
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(resp["b64"]))
    return out_path
