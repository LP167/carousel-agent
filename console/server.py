"""Review console: watch a run live, see every refusal, approve or send back with a note."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import loop  # noqa: E402
from agent.record import DeckRecord  # noqa: E402
from meta.client import Transport  # noqa: E402

RUNS = ROOT / "runs"
app = FastAPI()
app.mount("/files", StaticFiles(directory=str(RUNS)), name="files")
_busy: set[str] = set()


@app.get("/")
def index():
    return HTMLResponse((Path(__file__).parent / "index.html").read_text())


@app.get("/api/runs")
def runs():
    out = []
    for d in sorted(RUNS.iterdir(), reverse=True):
        if (d / "state.json").exists() and not d.name.startswith("_"):
            r = DeckRecord.load(d)
            out.append({"id": d.name, "status": r.status, "turns": r.turn})
    return out


def _rel(p: str) -> str:
    try:
        return "/files/" + str(Path(p).resolve().relative_to(RUNS.resolve()))
    except ValueError:
        return ""


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    d = RUNS / run_id
    if not (d / "state.json").exists():
        raise HTTPException(404)
    r = DeckRecord.load(d)
    slides = []
    for x in (r.render or {}).get("report", []):
        slides.append({"id": x["id"], "png": _rel(x["png"]), "problems": x["problems"]})
    return {"id": run_id, "status": r.status, "objective": r.objective, "timeline": r.timeline,
            "slides": slides, "render_version": (r.render or {}).get("version"), "stale": (r.render or {}).get("stale"),
            "flags": r.flags, "question": r.question, "outline_score": r.outline_score,
            "counters": r.counters, "busy": run_id in _busy}


class Note(BaseModel):
    note: str = ""


def _continue(run_id: str):
    d = RUNS / run_id
    try:
        rec = DeckRecord.load(d)
        t = Transport("record", replay_dir=d, usage_path=d / "usage.jsonl")
        t.n = len(list((d / "calls").glob("*.json"))) if (d / "calls").exists() else 0
        loop.run(rec, t, d)
    finally:
        _busy.discard(run_id)


@app.post("/api/runs/{run_id}/approve")
def approve(run_id: str):
    from run import publish_mock

    d = RUNS / run_id
    r = DeckRecord.load(d)
    if r.status != "awaiting_signoff":
        raise HTTPException(409, f"status is {r.status}")
    r.status = "approved"
    r.log("human_approve", {}, True, "approved")
    publish_mock(r, d)
    return {"ok": True}


@app.post("/api/runs/{run_id}/reject")
def reject(run_id: str, body: Note):
    d = RUNS / run_id
    r = DeckRecord.load(d)
    if run_id in _busy:
        raise HTTPException(409, "run is busy")
    r.human_notes.append(f"Reviewer rejected the deck: {body.note}")
    r.status = "running"
    r.counters["submit_rejects"] = 0
    if r.render:
        r.render["stale"] = True
    r.log("human_reject", {"note": body.note}, False, f"the reviewer sent the deck back: {body.note}")
    r.save(d)
    _busy.add(run_id)
    threading.Thread(target=_continue, args=(run_id,), daemon=True).start()
    return {"ok": True}
