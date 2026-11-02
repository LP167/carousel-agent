"""Smoke-test every Meta model this project depends on.

    python scripts/spike.py

Each check prints PASS/FAIL and writes raw outputs to runs/_spike/ so format
surprises can be fixed quickly. Costs a few cents of API credit.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meta import image, sam, spark, transcribe  # noqa: E402
from meta.client import Transport  # noqa: E402

OUT = ROOT / "runs" / "_spike"
OUT.mkdir(parents=True, exist_ok=True)
t = Transport("record", replay_dir=OUT / "replay", usage_path=OUT / "usage.jsonl")
results = {}


def check(name):
    def wrap(fn):
        try:
            detail = fn()
            results[name] = ("PASS", detail)
            print(f"PASS  {name}: {detail}")
        except Exception as e:  # noqa: BLE001
            results[name] = ("FAIL", repr(e))
            print(f"FAIL  {name}: {e!r}")
            (OUT / f"{name}.error.txt").write_text(traceback.format_exc())
        return fn
    return wrap


@check("models_list")
def _():
    ids = [m.id for m in t.openai.models.list().data]
    (OUT / "models.json").write_text(json.dumps(ids, indent=1))
    need = [t.cfg["models"][k] for k in ("brain", "image", "segment", "transcribe")]
    missing = [m for m in need if m not in ids]
    assert not missing, f"missing models: {missing}"
    return f"{len(ids)} models, all 4 needed present"


@check("spark_text")
def _():
    m = spark.chat(t, [{"role": "user", "content": "Reply with exactly: ready"}])
    return (m["content"] or "")[:60]


@check("spark_tool_call")
def _():
    tools = [{"type": "function", "function": {
        "name": "record_claim", "description": "Record one sentence with its quote.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "quote": {"type": "string"}},
                       "required": ["text", "quote"], "additionalProperties": False}}}]
    m = spark.chat(t, [{"role": "user", "content": "Source says: 'Our bottle keeps drinks cold for 24 hours.' Record one claim using the tool."}], tools=tools)
    assert m["tool_calls"], f"no tool call, content={m['content']!r}"
    c = m["tool_calls"][0]["function"]
    return f"{c['name']}({c['arguments'][:80]})"


@check("spark_json_schema")
def _():
    schema = {"type": "object", "properties": {"verdict": {"type": "string", "enum": ["supported", "overstated"]}},
              "required": ["verdict"], "additionalProperties": False}
    d = spark.ask_json(t, "You check claims.", [spark.text_part("Quote: 'cold for 24 hours'. Claim: 'cold for 48 hours'.")], schema, "v", "spike_schema")
    return d


@check("muse_image")
def _():
    p = image.generate(t, "studio product photo of a matte sage-green insulated water bottle on a plain warm beige background, soft light", OUT / "image.png")
    from PIL import Image
    im = Image.open(p)
    return f"{im.size} -> {p.name}"


@check("spark_vision")
def _():
    p = OUT / "image.png"
    assert p.exists(), "needs muse_image first"
    m = spark.chat(t, [{"role": "user", "content": [spark.text_part("In 8 words, what object is in this image?"), spark.image_part(p, 540)]}])
    return (m["content"] or "")[:80]


@check("sam_cutout")
def _():
    p = OUT / "image.png"
    assert p.exists(), "needs muse_image first"
    r = sam.cutout(t, p, "water bottle", OUT / "cutout.png")
    raw = sorted((OUT / "replay" / "calls").glob("*_sam.json"))
    assert r.get("ok"), f"{r} raw={raw[-1].read_text()[:300] if raw else None}"
    return r


@check("voice_transcribe")
def _():
    wav = OUT / "brief.wav"
    if not wav.exists():
        if not shutil.which("say"):
            raise RuntimeError("no test audio: put a WAV at runs/_spike/brief.wav")
        aiff = OUT / "brief.aiff"
        subprocess.run(["say", "-o", str(aiff), "This is a short test brief for a sage green water bottle."], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)], check=True)
    return transcribe.transcribe(t, wav)[:80]


print("\nSUMMARY:", {k: v[0] for k, v in results.items()})
(OUT / "summary.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str))
