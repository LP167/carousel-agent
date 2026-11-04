# Provenance

**Everything in this repository was written during the hackathon (Oct 27 – Nov 4, 2026).**

Before the hackathon, the author built a private tool that turned math-exam PDFs into Instagram card images
for one client. That tool is **not** in this repository: no code, assets, data, or git history from it were
copied. Only the lesson carried over — that the slow part of making a carousel is checking that the copy is
true and that every slide actually looks right — and this project is a new, general design around that lesson.

The "checks live inside the tools" principle follows the public talk pattern from Meta's Verifiable Agents
workshop; no workshop code was copied, and all file names, functions and prompts here are original.

All sample materials in `samples/` are fictional and were created for this project: the brand and product guide
were written by the author, the voice brief is the author's own recording, and `bottle_photo.png` was generated
with Muse Image (muse-image-1.0) as a stand-in for an owner's phone photo — no third-party photos are used. Fonts: Pretendard (SIL OFL 1.1). SAM output parsing uses Meta's
`meta-sam-parser` package as a dependency (installed from PyPI, not vendored).
