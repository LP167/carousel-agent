"""DeckRecord — the single source of truth for one run. Saved every turn."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

SLIDE_TYPES = ("cover", "point", "quote", "visual", "cta")


@dataclass
class DeckRecord:
    run_id: str
    objective: str
    brand: dict
    sources: dict = field(default_factory=dict)      # id -> {kind, path, title, pages[], read}
    outline: list = field(default_factory=list)      # [{id, type, title, kicker, source_refs[]}]
    claims: list = field(default_factory=list)       # [{id, slide_id, text, quotes[{source_id,page,quote}]}]
    assets: dict = field(default_factory=dict)       # slide_id -> {background?, cutout?}
    render: dict = field(default_factory=dict)       # {ok, version, report[]}
    counters: dict = field(default_factory=lambda: {"outline_rejects": 0, "submit_rejects": 0, "claim_seq": 0, "render_version": 0})
    flags: list = field(default_factory=list)
    timeline: list = field(default_factory=list)     # [{turn, tool, args, ok, observation, ts}]
    status: str = "running"                          # running|needs_input|needs_review|awaiting_signoff|approved|published|stopped
    question: str = ""
    human_notes: list = field(default_factory=list)
    outline_score: float | None = None
    turn: int = 0

    # -- persistence --------------------------------------------------------
    def save(self, run_dir: Path):
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        tmp = run_dir / "state.json.tmp"
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1))
        tmp.replace(run_dir / "state.json")

    @classmethod
    def load(cls, run_dir: Path) -> "DeckRecord":
        return cls(**json.loads((Path(run_dir) / "state.json").read_text()))

    # -- helpers ------------------------------------------------------------
    def slide(self, slide_id: str) -> dict | None:
        return next((s for s in self.outline if s["id"] == slide_id), None)

    def claims_for(self, slide_id: str) -> list:
        return [c for c in self.claims if c["slide_id"] == slide_id]

    def log(self, tool: str, args: dict, ok: bool, observation: str, think: str = ""):
        self.timeline.append({"turn": self.turn, "think": think, "tool": tool, "args": args, "ok": ok,
                              "observation": observation, "ts": time.time()})

    def summary(self) -> str:
        """Compact state for the model each turn."""
        lines = [f"STATUS: {self.status}"]
        lines.append("SOURCES: " + "; ".join(
            f"{sid} ({s['kind']}, {len(s.get('pages') or [])} pages{', READ' if s.get('read') else ', not read yet'})"
            for sid, s in self.sources.items()))
        if not self.outline:
            lines.append("OUTLINE: none yet (call set_outline after reading the sources)")
        else:
            lines.append(f"OUTLINE ({len(self.outline)} slides):")
            for s in self.outline:
                cs = self.claims_for(s["id"])
                a = self.assets.get(s["id"], {})
                lines.append(f"  - {s['id']} [{s['type']}] \"{s['title']}\" | {len(cs)} sentence(s)"
                             + (f" | assets: {', '.join(a)}" if a else ""))
                for c in cs:
                    lines.append(f"      {c['id']}: {c['text']}")
        r = self.render
        if r:
            bad = [x for x in r.get("report", []) if x["problems"]]
            lines.append(f"LAST RENDER v{r.get('version')}: {'passed' if r.get('ok') else f'{len(bad)} slide(s) with problems'}"
                         + (" (stale: content changed since)" if r.get("stale") else ""))
        lines.append(f"REJECTIONS: outline {self.counters['outline_rejects']}, submit {self.counters['submit_rejects']}")
        for n in self.human_notes[-3:]:
            lines.append(f"HUMAN NOTE: {n}")
        return "\n".join(lines)
