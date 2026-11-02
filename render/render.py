"""HTML → 1080×1350 PNG with Playwright, plus code-level render checks."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from meta.client import load_config

from .templates import slide_html

CHECKS_JS = (Path(__file__).parent / "checks.js").read_text()
NEEDS_FOOTER = {"point", "quote", "visual"}


def render_slides(slides: list[dict], brand: dict, out_dir: Path) -> list[dict]:
    """Render every slide; return per-slide {id, png, problems[]}."""
    from playwright.sync_api import sync_playwright

    cfg = load_config()["render"]
    w, h, m = cfg["width"], cfg["height"], cfg["safe_margin"]
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        for i, s in enumerate(slides, 1):
            html_path = out_dir / f"{i:02d}_{s['id']}.html"
            html_path.write_text(slide_html(s, brand, i, len(slides), w, h, m))
            page.goto(html_path.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_load_state("networkidle")
            meas = page.evaluate(CHECKS_JS, {"width": w, "height": h, "margin": m,
                                             "min_body_px": cfg["min_body_px"], "min_title_px": cfg["min_title_px"],
                                             "min_contrast": cfg["min_contrast"]})
            png = out_dir / f"{i:02d}_{s['id']}.png"
            page.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": w, "height": h})
            report.append({"id": s["id"], "png": str(png), "problems": _problems(s, meas, png, w, h)})
        browser.close()
    return report


def _problems(slide, meas, png, w, h) -> list[str]:
    probs = []
    if Image.open(png).size != (w, h):
        probs.append(f"size is {Image.open(png).size}, must be {w}x{h}")
    for o in meas["overflow"]:
        probs.append(f"text overflows its box by {o['hidden_px']}px (starts: '{o['text'][:40]}') — shorten it")
    for s in meas["small"]:
        probs.append(f"{s['role']} text is {s['px']}px, minimum {s['min']}px")
    for c in meas["contrast"]:
        probs.append(f"{c['role']} contrast {c['ratio']} below 4.5" + (f" ({c['note']})" if c.get("note") else ""))
    for g in meas["margin"]:
        probs.append(f"{g['role']} text outside the 72px safe margin at {g['box']}")
    for o in meas["overlap"]:
        probs.append(f"{o['role']} text overlaps the cutout image ({o['area']}px²)")
    if slide["type"] in NEEDS_FOOTER and not meas["footer"]:
        probs.append("missing source footer")
    if not meas["font_ok"]:
        probs.append("brand font did not load (fallback glyphs)")
    return probs


def preview(png: Path, size=(540, 675)) -> Path:
    out = Path(png).with_suffix(".qa.png")
    im = Image.open(png)
    im.thumbnail(size)
    im.save(out)
    return out
