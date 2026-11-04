# Carousel Agent

**An agent that turns a brand's own material into an Instagram carousel it can prove — every sentence quoted from the source, every slide looked at by Muse Spark before a human signs off.**

Built for the Meta Global AI Developer Hackathon · Indie track · *Build for Your World*.
All code was written during the hackathon — see [PROVENANCE.md](PROVENANCE.md).

## The problem

Small brands are told to post carousels every week. AI can write the copy, but the owner still has to check every
line against the product sheet ("did it say 24 hours or 48?") and click through every slide for cut-off text. That
checking is the actual bottleneck — so this agent is built around checks it cannot skip.

## What it does

```
product PDF / notes ─┐
voice brief (audio) ─┼─► read ─► plan ─► write (quoted) ─► visuals ─► render ─► submit ─► human sign-off ─► publish (mocked)
product photo ───────┘     │       │          │               │            │          │
                      Voice      outline   citation        SAM 3.1     layout     claim check (Spark)
                      Transcribe coverage  gate (code)     Muse Image  checks     visual check (Spark sees the PNGs)
```

The model chooses one tool per turn. **Each check lives inside its tool**, so the agent cannot route around it; a
refusal comes back as an observation and the agent fixes exactly what was named.

| Meta model | Role | What breaks without it |
|---|---|---|
| `muse-spark-1.3` | Agent brain (tool calling) · outline coverage judge · claim check (structured output) · **visual QA on the rendered PNGs (image input)** | Planning, writing and both final checks |
| `sam-3.1` | Cuts the product out of the owner's own photo for the visual slide | The visual slide has no product |
| `muse-image-1.0` | Generates the cover background in the brand palette | Cover falls back to a flat colour |
| `muse-voice-transcribe-1.0` | Turns the owner's voice memo into a **quotable source**. Facts that exist only in the owner's head (a launch price, a pop-up giveaway) become evidence the citation gate accepts | Spoken-only facts have no source to quote, so they cannot enter the carousel |

### The checks

| Where | Check | Kind |
|---|---|---|
| `set_outline` | Hidden key points (extracted by a separate Spark call the agent never sees) must be ≥70% covered; 7–9 slides, cover first, CTA last. Feedback names only the *kind* of thing missing | Spark + code |
| `record_claim` | **Citation gate:** each quote must appear word-for-word on the page it cites (≥15 chars, normalised) — PDFs and the voice transcript alike. Every number in the sentence must also appear in its quotes | code |
| `render_deck` | Overflow, min font size, WCAG contrast, 72px safe margin, source footer, cutout/text overlap, font loaded | code (Playwright) |
| `submit_deck` ① | Rules: every slide filled, numbers in headlines backed by a quote, fresh render | code |
| `submit_deck` ② | **Claim check:** does each quote really support its sentence? (`supported / overstated / unsupported`) | Spark |
| `submit_deck` ③ | **Visual check:** Spark looks at every rendered slide image and compares it to the text that should be there (clipped, unreadable, mismatch, overlap, bad cutout) | Spark (vision) |
| after 3 rejections | Stops and asks for human review instead of looping | code |

Before sign-off the full voice transcript is shown to the human, because a misheard number would otherwise become "evidence".

Instagram publishing is **mocked**: approval writes the carousel payload to `runs/<id>/published.json`.

## Run it

```bash
./scripts/setup.sh                    # venv, deps, Chromium; creates .env
# put your key in .env → MODEL_API_KEY=...
. .venv/bin/activate
python scripts/spike.py               # optional: checks all 4 Meta models respond
python run.py new samples/brand_sol   # live run (also records every model response)
python run.py console                 # http://127.0.0.1:8765 — timeline, slides, approve / send back
```

**No API key?** Replay a recorded run — same tools, same checks, same rendering, model responses read from disk:

```bash
python run.py replay replay/brand_sol_live   # recorded live run, Nov 4 2026: 27 turns, 2 refusals
```

Tests (offline, scripted model): `python -m pytest -q`

## Repository map

```
agent/loop.py            one tool per turn, state saved every turn, resumable
agent/tools/             one file per tool; each check is called from inside its tool
agent/verification/      citation gate, outline coverage, rules, claim check, visual check
meta/                    thin clients for Spark, SAM 3.1, Muse Image, Voice Transcribe + record/replay transport
render/                  5 HTML slide layouts → 1080×1350 PNG, layout checks in checks.js
console/                 review UI (FastAPI + one HTML file)
samples/brand_sol/       fictional brand: product guide PDF, owner's voice memo (states a launch price not in the PDF), product photo
```

## Samples and rights

Every file in `samples/` is fictional and made by the author for this project. No third-party brand material is used.
