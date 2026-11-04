"""Whole agent loop offline: scripted model decisions, real tools, real checks, real rendering."""
import shutil
import wave
from pathlib import Path

from agent import loop
from agent.record import DeckRecord
from agent.sources import discover
from tests.fakes import FakeTransport, js, photo, png_b64, sam_text, tool

ROOT = Path(__file__).resolve().parents[1]
BRIEF = "Hi, it's Mina from SOL. Keep it friendly, and remind people the lid can go in the dishwasher but the body cannot."


def sample(tmp: Path) -> Path:
    d = tmp / "brand_test"
    shutil.copytree(ROOT / "samples" / "brand_sol", d, ignore=shutil.ignore_patterns("*.m4a", "*.wav", "*.jpg", "*.png"))
    shutil.copy(photo(), d / "bottle_photo.png")
    with wave.open(str(d / "voice_brief.wav"), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(b"\0\0" * 1600)
    return d


def claim(slide, text, quotes=(), replaces=""):
    return tool("record_claim", slide_id=slide, text=text, replaces=replaces,
                quotes=[{"source_id": s, "page": p, "quote": q} for s, p, q in quotes])


G = "product_guide"
OUTLINE = [
    {"type": "cover", "title": "Your desk needs a better bottle", "kicker": "SOL"},
    {"type": "point", "title": "Still cold at 4 pm", "kicker": "Temperature"},
    {"type": "point", "title": "Steel where it matters", "kicker": "Materials"},
    {"type": "visual", "title": "Meet the Everyday Bottle", "kicker": "Product"},
    {"type": "quote", "title": "From a tester", "kicker": "Testers"},
    {"type": "point", "title": "Easy to care for", "kicker": "Care"},
    {"type": "cta", "title": "Find it in Seongsu", "kicker": "Buy"},
]
KPS = {"keypoints": [{"point": p, "category": c} for p, c in [
    ("cold 24h / hot 12h", "spec"), ("18/8 steel, BPA-free lid", "spec"), ("care: lid dishwasher, body hand wash", "other"),
    ("tester quote", "proof"), ("price 32,000 won", "price_or_terms"), ("where to buy", "other")]]}
COV_BAD = {"coverage": [{"index": i, "covered_by": s} for i, s in enumerate(["s2", "none", "none", "none", "none", "none"])]}
COV_OK = {"coverage": [{"index": i, "covered_by": s} for i, s in enumerate(["s2", "s3", "s6", "s5", "none", "s7"])]}

SCRIPT = {
    "agent": [
        tool("read_source", source_id=G),
        tool("read_source", source_id="voice_brief"),
        tool("read_source", source_id="bottle_photo"),
        tool("set_outline", slides=OUTLINE[:2] + OUTLINE[-1:]),                    # refused: shape + coverage
        tool("set_outline", slides=OUTLINE),
        claim("s1", "Drink more water without thinking about it"),
        claim("s2", "Drinks stay cold all day, every day", [(G, 1, "keeps drinks cold all day")]),  # refused: not on page
        claim("s2", "Cold drinks for up to 24 hours", [(G, 1, "keeps drinks cold for up to 24 hours")]),
        claim("s2", "Measured at 22°C with the lid closed", [(G, 1, "measured this at a room temperature of 22°C with the lid closed")]),
        claim("s3", "18/8 stainless steel body, BPA-free lid", [(G, 1, "The body is made of 18/8 stainless steel"), (G, 1, "The lid is made of BPA-free polypropylene")]),
        claim("s3", "Lid made of BPA-free polypropylene", [(G, 1, "The lid is made of BPA-free polypropylene with a silicone seal")]),
        claim("s4", "500 ml, 310 g, fits a cup holder", [(G, 1, "The bottle holds 500 ml and weighs 310 g empty")]),
        claim("s5", "I finally drink water at my desk because it is still cold at 4 pm.", [(G, 2, "I finally drink water at my desk because it is still cold at 4 pm")]),
        claim("s6", "Lid in the dishwasher, body by hand", [(G, 2, "Hand wash the body with warm water and mild soap. The lid is top-rack dishwasher safe")]),
        claim("s6", "Do not put the body in the dishwasher", [(G, 2, "Do not put the body in the dishwasher")]),
        claim("s7", "Pop-up in Seongsu-dong on November weekends", [(G, 2, "visit our pop-up at Seongsu-dong on weekends in November")]),
        tool("request_visual", slide_id="s4", kind="cutout", prompt="water bottle", source_id="bottle_photo"),
        tool("request_visual", slide_id="s1", kind="background", prompt="sunlit office desk", source_id=""),
        tool("render_deck"),
        tool("submit_deck", summary="7 slides"),                                   # claim check rejects c2
        claim("s2", "Cold drinks for up to 24 hours", [(G, 1, "keeps drinks cold for up to 24 hours")], replaces="c2"),
        tool("render_deck"),
        tool("submit_deck", summary="7 slides"),                                   # visual check rejects
        claim("s4", "500 ml and 310 g empty", [(G, 1, "The bottle holds 500 ml and weighs 310 g empty")], replaces="c6"),
        tool("render_deck"),
        tool("submit_deck", summary="7 slides"),
    ],
    "transcribe": [{"text": BRIEF}],
    "verify_outline_keypoints": [js(KPS)],
    "verify_outline_coverage": [js(COV_BAD), js(COV_OK)],
    "sam": [{"text": sam_text()}],
    "image": [{"b64": png_b64()}],
    "verify_claims": [
        js({"results": [{"claim_id": "c2", "verdict": "overstated", "reason": "quote says 'up to 24 hours'; sentence drops the condition"}]}),
        js({"results": []}), js({"results": []})],
    "verify_visual": [
        js({"slides": [{"slide_id": "s4", "issues": [{"kind": "overlap", "severity": "block", "note": "caption crowds the bottle"}]}]}),
        js({"slides": []})],
}


def test_full_run_with_refusals(tmp_path):
    objective, brand, sources = discover(sample(tmp_path))
    rec = DeckRecord(run_id="t", objective=objective, brand=brand, sources=sources)
    t = FakeTransport(SCRIPT, record_to=tmp_path / "run")
    rec = loop.run(rec, t, tmp_path / "run")
    refused = [(e["tool"], e["observation"].splitlines()[0]) for e in rec.timeline if not e["ok"]]
    for line in refused:
        print(line)
    assert rec.status == "awaiting_signoff", rec.timeline[-1]
    tools_refused = [r[0] for r in refused]
    assert tools_refused[:2] == ["set_outline", "record_claim"]
    assert "citation refused" in refused[1][1]
    assert sum(r[0] == "submit_deck" for r in refused) == 2
    assert rec.sources["voice_brief"]["pages"] == [BRIEF]
    assert Path(rec.assets["s4"]["cutout"]).exists()
    assert len(rec.render["report"]) == 7 and rec.render["ok"]

    # the same run replays from its recording with no API access
    from meta.client import Transport
    objective, brand, sources = discover(sample(tmp_path / "again"))
    rec2 = DeckRecord(run_id="r", objective=objective, brand=brand, sources=sources)
    rec2 = loop.run(rec2, Transport("replay", replay_dir=tmp_path / "run"), tmp_path / "replayed")
    assert rec2.status == "awaiting_signoff"
    assert [e["tool"] for e in rec2.timeline] == [e["tool"] for e in rec.timeline]
