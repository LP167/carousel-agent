"""Tool registry. The model picks exactly one tool per turn; each check lives inside its tool."""
from dataclasses import dataclass
from pathlib import Path

from . import (ask_human, read_source, record_claim, remove_claim, render_deck, request_visual, set_outline,
               submit_deck)

TOOLS = {m.SPEC["name"]: m for m in (read_source, set_outline, record_claim, remove_claim, request_visual,
                                     render_deck, submit_deck, ask_human)}


@dataclass
class Ctx:
    record: object
    t: object
    run_dir: Path
    cfg: dict


def definitions():
    return [{"type": "function", "function": {**m.SPEC, "strict": True}} for m in TOOLS.values()]


def run(name: str, args: dict, ctx: Ctx):
    if name not in TOOLS:
        return False, f"unknown tool '{name}'. Tools: {', '.join(TOOLS)}"
    try:
        return TOOLS[name].run(args, ctx)
    except KeyError as e:
        return False, f"missing argument {e}"
