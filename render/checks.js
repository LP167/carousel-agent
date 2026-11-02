// Runs inside the rendered page. Returns measurements; Python decides pass/fail.
(cfg) => {
  const out = { overflow: [], small: [], contrast: [], margin: [], overlap: [], footer: null, font_ok: null };
  const W = cfg.width, H = cfg.height, M = cfg.margin;

  const parseRGB = (s) => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x)); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = (c) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };

  // background behind an element: nearest ancestor with an opaque-ish background colour
  const bgOf = (el) => { let e = el; while (e) { const c = parseRGB(getComputedStyle(e).backgroundColor);
      if (c && c.a > 0.85) return { c, overImage: false }; e = e.parentElement; }
    return { c: parseRGB(getComputedStyle(document.body).backgroundColor), overImage: !!document.querySelector('.bgimg') }; };

  document.querySelectorAll('[data-fit]').forEach((el, i) => {
    if (el.scrollHeight > el.clientHeight + 1) out.overflow.push({ i, hidden_px: el.scrollHeight - el.clientHeight, text: el.innerText.slice(0, 60) });
  });

  const texts = [...document.querySelectorAll('[data-role]')].filter(e => e.dataset.role !== 'cutout' && e.innerText.trim());
  texts.forEach(el => {
    const role = el.dataset.role, cs = getComputedStyle(el), px = parseFloat(cs.fontSize);
    const min = role === 'title' ? cfg.min_title_px : (role === 'kicker' || role === 'footer' ? 26 : cfg.min_body_px);
    if (px < min) out.small.push({ role, px, min });
    const bg = bgOf(el), fg = parseRGB(cs.color);
    if (bg.overImage) out.contrast.push({ role, ratio: 0, note: 'text directly on image without a panel' });
    else if (fg && bg.c) { const r = ratio(fg, bg.c); if (r < cfg.min_contrast) out.contrast.push({ role, ratio: +r.toFixed(2) }); }
    const b = el.getBoundingClientRect();
    if (b.left < M - 1 || b.top < M - 1 || b.right > W - M + 1 || b.bottom > H - M + 1)
      out.margin.push({ role, box: [b.left, b.top, b.right, b.bottom].map(Math.round) });
  });

  const cut = document.querySelector('[data-role=cutout]');
  if (cut) { const c = cut.getBoundingClientRect();
    texts.forEach(el => { const b = el.getBoundingClientRect();
      const ix = Math.max(0, Math.min(b.right, c.right) - Math.max(b.left, c.left));
      const iy = Math.max(0, Math.min(b.bottom, c.bottom) - Math.max(b.top, c.top));
      if (ix * iy > 0) out.overlap.push({ role: el.dataset.role, area: Math.round(ix * iy) }); }); }

  const f = document.querySelector('[data-role=footer]');
  out.footer = f ? f.innerText.trim() : '';
  out.font_ok = [...document.fonts].some(ff => ff.family.includes('Pretendard') && ff.status === 'loaded');
  return out;
}
