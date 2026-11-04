#!/usr/bin/env python3
"""carousel-agent CLI.

  python run.py new samples/brand_sol          live run (every model call is also recorded for replay)
  python run.py resume <run_id>                continue a stopped run
  python run.py answer <run_id> "text"         answer an ask_human question and continue
  python run.py approve <run_id>               human sign-off → mock publish
  python run.py reject <run_id> "note"         send the deck back with a note; the agent continues
  python run.py replay <run_dir>               re-run a recorded run with no API key
  python run.py console                        open the review console (http://127.0.0.1:8765)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent import loop  # noqa: E402
from agent.record import DeckRecord  # noqa: E402
from agent.sources import discover  # noqa: E402
from meta.client import Transport  # noqa: E402

RUNS = ROOT / "runs"
C = {"ok": "\033[32m", "no": "\033[31m", "dim": "\033[2m", "b": "\033[1m", "x": "\033[0m"}


def show(e, rec):
    mark = f"{C['ok']}✔{C['x']}" if e["ok"] else f"{C['no']}✘ REFUSED{C['x']}"
    args = json.dumps(e["args"], ensure_ascii=False)
    print(f"{C['dim']}turn {e['turn']:>2}{C['x']} {C['b']}{e['tool']}{C['x']} {args[:140]}")
    first = e["observation"].splitlines()[0] if e["observation"] else ""
    print(f"        {mark} {first[:200]}")
    for line in e["observation"].splitlines()[1:6]:
        if not e["ok"]:
            print(f"          {C['no']}{line[:200]}{C['x']}")


def transport(run_dir: Path, mode="record", replay_from: Path | None = None):
    return Transport(mode, replay_dir=replay_from or run_dir, usage_path=run_dir / "usage.jsonl")


def finish(rec, run_dir):
    print(f"\n{C['b']}status: {rec.status}{C['x']}  run: {run_dir.name}")
    if rec.status == "needs_input":
        print(f"question: {rec.question}\n→ python run.py answer {run_dir.name} \"...\"")
    if rec.status == "awaiting_signoff":
        for sid, s in rec.sources.items():
            if s["kind"] == "audio" and s.get("pages"):
                print(f"\n{C['b']}Voice brief transcript ({sid}) - check names and numbers before approving:{C['x']}\n  {s['pages'][0]}\n")
        print(f"slides: {run_dir / 'render' / ('v' + str(rec.render['version']))}\n→ python run.py approve {run_dir.name}   or   reject {run_dir.name} \"note\"")
    for f in rec.flags:
        print(f"flag: {f}")


def cmd_new(sample):
    objective, brand, sources = discover(Path(sample))
    run_id = time.strftime("%m%d-%H%M%S") + "-" + Path(sample).name
    run_dir = RUNS / run_id
    rec = DeckRecord(run_id=run_id, objective=objective, brand=brand, sources=sources)
    rec.save(run_dir)
    print(f"run {run_id}: {len(sources)} sources → {', '.join(sources)}\n")
    rec = loop.run(rec, transport(run_dir), run_dir, show)
    finish(rec, run_dir)


def _load(run_id):
    run_dir = RUNS / run_id if not Path(run_id).exists() else Path(run_id)
    return DeckRecord.load(run_dir), run_dir


def _continue(rec, run_dir):
    # live calls after a resume are appended to the same recording, continuing its numbering
    t = transport(run_dir)
    t.n = len(list((run_dir / "calls").glob("*.json"))) if (run_dir / "calls").exists() else 0
    rec = loop.run(rec, t, run_dir, show)
    finish(rec, run_dir)


def cmd_resume(run_id):
    rec, run_dir = _load(run_id)
    if rec.status == "stopped":
        rec.status = "running"
    _continue(rec, run_dir)


def cmd_answer(run_id, text):
    rec, run_dir = _load(run_id)
    rec.human_notes.append(f"Answer to '{rec.question}': {text}")
    rec.question, rec.status = "", "running"
    rec.log("human_answer", {"text": text}, True, "the human answered; continue")
    _continue(rec, run_dir)


def cmd_reject(run_id, note):
    rec, run_dir = _load(run_id)
    rec.human_notes.append(f"Reviewer rejected the deck: {note}")
    rec.status = "running"
    rec.counters["submit_rejects"] = 0
    rec.render["stale"] = True
    rec.log("human_reject", {"note": note}, False, f"the reviewer sent the deck back: {note}")
    _continue(rec, run_dir)


def cmd_approve(run_id):
    rec, run_dir = _load(run_id)
    if rec.status != "awaiting_signoff":
        sys.exit(f"cannot approve: status is {rec.status}")
    rec.status = "approved"
    rec.log("human_approve", {}, True, "approved")
    publish_mock(rec, run_dir)
    finish(rec, run_dir)


def publish_mock(rec, run_dir):
    """Instagram publishing is MOCKED: we write the payload a Graph API call would carry."""
    v = rec.render["version"]
    payload = {"mocked": True, "note": "Instagram publishing is simulated in this hackathon build.",
               "media_type": "CAROUSEL", "children": [r["png"] for r in rec.render["report"]],
               "caption": rec.outline[0]["title"]}
    (run_dir / "published.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    rec.status = "published"
    rec.save(run_dir)
    print(f"mock-published render v{v} → {run_dir / 'published.json'}")


def cmd_replay(src):
    src = Path(src)
    first = json.loads((src / "state.json").read_text())
    run_id = time.strftime("%m%d-%H%M%S") + "-replay"
    run_dir = RUNS / run_id
    # re-discover the sample files on this machine (recorded paths belong to the recording machine)
    sample = ROOT / "samples" / first["run_id"].split("-", 2)[2]
    _, _, sources = discover(sample)
    rec = DeckRecord(run_id=run_id, objective=first["objective"], brand=first["brand"], sources=sources)
    rec.save(run_dir)
    print(f"REPLAY of {src.name} (recorded model responses, no API key used)\n")
    rec = loop.run(rec, transport(run_dir, "replay", src), run_dir, show)
    finish(rec, run_dir)


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    c, rest = argv[1], argv[2:]
    if c == "new":
        cmd_new(rest[0])
    elif c == "resume":
        cmd_resume(rest[0])
    elif c == "answer":
        cmd_answer(rest[0], rest[1])
    elif c == "approve":
        cmd_approve(rest[0])
    elif c == "reject":
        cmd_reject(rest[0], rest[1])
    elif c == "replay":
        cmd_replay(rest[0])
    elif c == "console":
        import uvicorn
        uvicorn.run("console.server:app", host="127.0.0.1", port=8765)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
