"""Five slide layouts as HTML. The renderer only reads the DeckRecord, never free text.

Every text node carries data-role (title | body | quote | caption | footer | kicker)
so render/checks.py can measure it.
"""
from __future__ import annotations

import html
from pathlib import Path

FONT_DIR = Path(__file__).parent / "fonts"

DEFAULT_BRAND = {
    "name": "Brand",
    "bg": "#F4EFE6",
    "ink": "#1F2A24",
    "accent": "#3E6B55",
    "muted": "#5E6B63",
    "panel": "#FFFFFF",
}


def _css(brand: dict, w: int, h: int, margin: int) -> str:
    faces = "".join(
        f"@font-face{{font-family:'Pretendard';src:url('{(FONT_DIR / f'Pretendard-{name}.woff2').as_uri()}') format('woff2');font-weight:{wt};}}"
        for name, wt in (("Regular", 400), ("SemiBold", 600), ("Bold", 700), ("ExtraBold", 800))
    )
    b = {**DEFAULT_BRAND, **brand}
    return faces + f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{w}px;height:{h}px;overflow:hidden}}
body{{font-family:'Pretendard',sans-serif;background:{b['bg']};color:{b['ink']};word-break:keep-all;overflow-wrap:break-word}}
.slide{{position:relative;width:{w}px;height:{h}px;padding:{margin}px;display:flex;flex-direction:column}}
.bgimg{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:0}}
.layer{{position:relative;z-index:1;display:flex;flex-direction:column;height:100%}}
[data-role=kicker]{{font-size:30px;font-weight:700;letter-spacing:.04em;color:{b['accent']};text-transform:uppercase}}
[data-role=title]{{font-size:76px;line-height:1.15;font-weight:800;letter-spacing:-.02em}}
[data-role=body]{{font-size:40px;line-height:1.45;font-weight:400}}
[data-role=quote]{{font-size:58px;line-height:1.3;font-weight:700;letter-spacing:-.01em}}
[data-role=caption]{{font-size:36px;line-height:1.4;font-weight:600}}
[data-role=footer]{{font-size:30px;color:{b['muted']};font-weight:600}}
.fit{{overflow:hidden}}
.grow{{flex:1;min-height:0}}
.panel{{background:{b['panel']};border-radius:28px;padding:48px}}
.bar{{width:96px;height:10px;background:{b['accent']};border-radius:5px;margin:28px 0}}
.pageno{{position:absolute;right:{margin}px;top:{margin}px;font-size:30px;font-weight:700;color:{b['muted']};z-index:2}}
.cutwrap{{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;margin:24px 0}}
.cutwrap img{{max-width:100%;max-height:100%;object-fit:contain}}
"""


def _e(s) -> str:
    return html.escape(str(s or ""))


def _paras(lines, role="body"):
    return "".join(f'<p data-role="{role}" style="margin-bottom:22px">{_e(x)}</p>' for x in lines)


def slide_html(slide: dict, brand: dict, index: int, total: int, w=1080, h=1350, margin=72) -> str:
    """slide = {type, title, lines[], footer, background?, cutout?}"""
    typ = slide["type"]
    title, lines, footer = slide.get("title", ""), slide.get("lines", []), slide.get("footer", "")
    bg = slide.get("background")
    bg_tag = f'<img class="bgimg" src="{Path(bg).as_uri()}">' if bg else ""
    pageno = f'<div class="pageno">{index}/{total}</div>' if typ != "cover" else ""
    foot = f'<div data-role="footer" style="margin-top:24px">{_e(footer)}</div>' if footer else ""

    if typ == "cover":
        inner = f"""{bg_tag}<div class="layer"><div class="grow"></div>
          <div class="panel fit" data-fit>
            <div data-role="kicker">{_e(brand.get('name',''))}</div>
            <div class="bar"></div>
            <div data-role="title">{_e(title)}</div>
            {_paras(lines[:1])}
          </div></div>"""
    elif typ == "point":
        inner = f"""{bg_tag}<div class="layer">
          <div data-role="kicker">{_e(slide.get('kicker','Point'))}</div><div class="bar"></div>
          <div data-role="title" class="fit" data-fit style="max-height:360px">{_e(title)}</div>
          <div class="grow fit" data-fit style="margin-top:40px">{_paras(lines)}</div>
          {foot}</div>"""
    elif typ == "quote":
        q = lines[0] if lines else ""
        inner = f"""{bg_tag}<div class="layer"><div class="grow"></div>
          <div data-role="kicker">{_e(title or 'In their words')}</div><div class="bar"></div>
          <div class="fit" data-fit style="max-height:760px"><p data-role="quote">“{_e(q)}”</p>{_paras(lines[1:])}</div>
          <div class="grow"></div>{foot}</div>"""
    elif typ == "visual":
        cut = slide.get("cutout")
        img = f'<img data-role="cutout" src="{Path(cut).as_uri()}">' if cut else ""
        inner = f"""{bg_tag}<div class="layer">
          <div data-role="kicker">{_e(slide.get('kicker','Product'))}</div><div class="bar"></div>
          <div data-role="title" class="fit" data-fit style="max-height:190px">{_e(title)}</div>
          <div class="cutwrap">{img}</div>
          <div class="fit" data-fit style="max-height:260px">{_paras(lines, 'caption')}</div>
          {foot}</div>"""
    elif typ == "cta":
        inner = f"""{bg_tag}<div class="layer"><div class="grow"></div>
          <div class="panel fit" data-fit>
            <div data-role="title">{_e(title)}</div><div class="bar"></div>{_paras(lines)}
          </div><div class="grow"></div>{foot}</div>"""
    else:
        raise ValueError(f"unknown slide type {typ}")

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_css(brand, w, h, margin)}</style></head>
<body><div class="slide" data-type="{typ}">{pageno}{inner}</div></body></html>"""
