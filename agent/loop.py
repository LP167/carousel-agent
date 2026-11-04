"""The agent loop: model decides → tool runs (with its checks inside) → observation goes back.

Each turn is stateless for the model: playbook + objective + compact record summary
+ the last few observations. That keeps context small and makes any run resumable.
"""
from __future__ import annotations

import json
from pathlib import Path

from meta import spark
from meta.client import Transport, load_config

from . import tools
from .record import DeckRecord

PLAYBOOK = (Path(__file__).parent / "playbook.md").read_text()
STOP = {"needs_input", "needs_review", "awaiting_signoff", "approved", "published", "stopped"}


def _messages(rec: DeckRecord) -> list:
    recent = rec.timeline[-4:]
    obs = "\n\n".join(
        f"[turn {e['turn']}] {e['tool']}({json.dumps(e['args'], ensure_ascii=False)[:300]}) → {'OK' if e['ok'] else 'REFUSED'}: {e['observation'][:4000]}"
        for e in recent) or "(nothing yet — start by reading the sources)"
    texts = []
    for sid, s in rec.sources.items():
        if s.get("read") and s.get("pages"):
            label = "owner's voice brief transcript" if s["kind"] == "audio" else s["title"]
            texts.append(f"=== {sid} ({label}) ===\n" + "\n".join(f"--- page {i+1} ---\n{p}" for i, p in enumerate(s["pages"])))
    src = ("SOURCES ALREADY READ (quote from these; no need to read them again):\n" + "\n\n".join(texts)[:40000] + "\n\n") if texts else ""
    user = f"OBJECTIVE:\n{rec.objective}\n\n{src}CURRENT STATE:\n{rec.summary()}\n\nRECENT RESULTS:\n{obs}\n\nChoose the next single tool call."
    return [{"role": "system", "content": PLAYBOOK}, {"role": "user", "content": user}]


def step(rec: DeckRecord, t: Transport, run_dir: Path, cfg: dict, on_event=None) -> None:
    rec.turn += 1
    msg = spark.chat(t, _messages(rec), tools=tools.definitions(), kind="agent")
    think = (msg.get("content") or "").strip()
    calls = msg.get("tool_calls") or []
    if not calls:
        rec.log("(none)", {}, False, "You must call exactly one tool each turn.", think)
    else:
        fn = calls[0]["function"]
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError as e:
            rec.log(fn["name"], {}, False, f"arguments were not valid JSON: {e}", think)
        else:
            ok, obs = tools.run(fn["name"], args, tools.Ctx(rec, t, run_dir, cfg))
            if len(calls) > 1:
                obs += f"\n(note: only the first of {len(calls)} tool calls was run)"
            rec.log(fn["name"], args, ok, obs, think)
    rec.save(run_dir)
    if on_event:
        on_event(rec.timeline[-1], rec)


def run(rec: DeckRecord, t: Transport, run_dir: Path, on_event=None) -> DeckRecord:
    cfg = load_config()
    rec.status = "running" if rec.status in ("running", "needs_input") else rec.status
    while rec.status not in STOP:
        if rec.turn >= cfg["agent"]["max_turns"]:
            rec.status = "stopped"
            rec.flags.append(f"turn limit {cfg['agent']['max_turns']} reached")
            break
        step(rec, t, run_dir, cfg, on_event)
    rec.save(run_dir)
    return rec
