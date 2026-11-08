"""Dependency-free SVG charts for static HTML reports.

Design rules (thin marks, recessive grid, one axis, legend for two or more series,
hover tooltips plus a data table so nothing depends on hovering or on colour alone)
follow a validated categorical palette with separate light and dark steps.
"""
from __future__ import annotations

from html import escape
import math

CSS = """
.viz{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--band:rgba(42,120,214,.08);margin:18px 0 26px;background:var(--surface);
border:1px solid rgba(11,11,11,.10);border-radius:12px;padding:16px 18px 10px;color:var(--ink)}
@media (prefers-color-scheme:dark){.viz{--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--band:rgba(57,135,229,.14);border-color:rgba(255,255,255,.10)}}
.viz h3{margin:0 0 2px;font-size:1rem}.viz .sub{margin:0 0 10px;color:var(--ink2);font-size:.88rem}
.viz svg{width:100%;max-width:900px;height:auto;display:block;font:12px system-ui,-apple-system,"Segoe UI",sans-serif}
.viz .tick{fill:var(--muted);font-variant-numeric:tabular-nums}.viz .lab{fill:var(--ink2)}.viz .val{fill:var(--ink);font-weight:600;paint-order:stroke;stroke:var(--surface);stroke-width:4px;stroke-linejoin:round}
.viz .grid{stroke:var(--grid);stroke-width:1}.viz .axis{stroke:var(--axis);stroke-width:1}
.viz .legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.85rem;color:var(--ink2);margin:4px 0 6px}
.viz .key{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle;margin-right:6px}
.viz .key.dot{width:9px;height:9px;border-radius:50%}.viz .key.hollow{background:transparent!important;border:2px solid var(--s2)}
.viz [data-tip]{cursor:default;outline:none}.viz [data-tip]:hover>.mark,.viz [data-tip]:focus>.mark{opacity:.78}
.viz details{margin-top:6px;font-size:.85rem}.viz summary{cursor:pointer;color:var(--ink2)}
.viz table{border-collapse:collapse;width:100%;margin-top:6px;font-variant-numeric:tabular-nums}
.viz th,.viz td{border-bottom:1px solid var(--grid);padding:5px 8px;text-align:left}
.viztip{position:fixed;pointer-events:none;z-index:9;background:#0b0b0b;color:#f0efec;padding:7px 10px;border-radius:8px;
font:12px/1.45 system-ui,sans-serif;max-width:300px;box-shadow:0 4px 16px rgba(0,0,0,.25);display:none;white-space:pre-line}
"""

SCRIPT = """<script>(()=>{const t=document.createElement('div');t.className='viztip';document.body.appendChild(t);
const show=(el,x,y)=>{t.textContent=el.getAttribute('data-tip');t.style.display='block';
const w=t.offsetWidth,h=t.offsetHeight;t.style.left=Math.min(innerWidth-w-8,x+14)+'px';t.style.top=Math.max(8,y-h-10)+'px'};
document.querySelectorAll('.viz [data-tip]').forEach(el=>{el.setAttribute('tabindex','0');
el.addEventListener('pointermove',e=>show(el,e.clientX,e.clientY));el.addEventListener('pointerleave',()=>t.style.display='none');
el.addEventListener('focus',()=>{const r=el.getBoundingClientRect();show(el,r.left+r.width/2,r.top)});
el.addEventListener('blur',()=>t.style.display='none')})})();</script>"""

SLOTS = ("var(--s1)", "var(--s2)", "var(--s3)")


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    exponent = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * exponent:
            return step * exponent
    return 10 * exponent


def _ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    span = _nice_max((hi - lo) / count)
    start = math.floor(lo / span) * span
    ticks, value = [], start
    while value <= hi + span * 1e-9:
        ticks.append(round(value, 10))
        value += span
    return ticks


def _rounded_bar(x: float, y: float, w: float, h: float, horizontal: bool, r: float = 4) -> str:
    """Bar path with a rounded data end and a square baseline end."""
    if horizontal:
        r = min(r, w / 2, h / 2)
        return (f"M{x:.1f},{y:.1f}h{w - r:.1f}a{r},{r} 0 0 1 {r},{r}v{h - 2 * r:.1f}"
                f"a{r},{r} 0 0 1 -{r},{r}h-{w - r:.1f}z")
    r = min(r, w / 2, h / 2)
    return (f"M{x:.1f},{y + h:.1f}v-{h - r:.1f}a{r},{r} 0 0 1 {r},-{r}h{w - 2 * r:.1f}"
            f"a{r},{r} 0 0 1 {r},{r}v{h - r:.1f}z")


def _figure(title: str, subtitle: str, svg: str, table_head: list[str], table_rows: list[list[str]],
            legend: str = "") -> str:
    head = "".join(f"<th scope='col'>{escape(h)}</th>" for h in table_head)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in row) + "</tr>" for row in table_rows)
    return (f"<figure class='viz'><h3>{escape(title)}</h3><p class='sub'>{escape(subtitle)}</p>{legend}{svg}"
            f"<details><summary>Show data table</summary><table><thead><tr>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table></details></figure>")


def _legend(items: list[tuple[str, str, str]]) -> str:
    keys = "".join(f"<span><i class='key {kind}' style='background:{colour}'></i>{escape(name)}</span>"
                   for name, colour, kind in items)
    return f"<div class='legend'>{keys}</div>"


def hbar(title: str, subtitle: str, rows: list[tuple[str, float, str]], fmt, value_label: str,
         highlight: set[str] | None = None, reference: tuple[float, str] | None = None) -> str:
    """Horizontal bars, one series. ``rows`` are (label, value, tooltip)."""
    highlight = highlight or set()
    width, label_w, right = 900, 230, 80
    bar_h, gap = 18, 10
    top = 22 if reference else 6
    height = top + len(rows) * (bar_h + gap) + 24
    vmax = _nice_max(max([v for _, v, _ in rows] + [reference[0] if reference else 0]))
    plot_w = width - label_w - right
    scale = lambda v: plot_w * v / vmax
    parts = [f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>"]
    for tick in _ticks(0, vmax, 4):
        x = label_w + scale(tick)
        parts.append(f"<line class='grid' x1='{x:.1f}' x2='{x:.1f}' y1='{top}' y2='{height - 20}'/>"
                     f"<text class='tick' x='{x:.1f}' y='{height - 6}' text-anchor='middle'>{escape(fmt(tick))}</text>")
    for i, (label, value, tip) in enumerate(rows):
        y = top + i * (bar_h + gap)
        colour = SLOTS[1] if label in highlight else SLOTS[0]
        w = max(scale(value), 2)
        parts.append(
            f"<g data-tip='{escape(tip)}'><rect x='0' y='{y - gap / 2}' width='{width}' height='{bar_h + gap}' fill='transparent'/>"
            f"<text class='lab' x='{label_w - 10}' y='{y + bar_h * .72:.1f}' text-anchor='end'>{escape(label)}</text>"
            f"<path class='mark' d='{_rounded_bar(label_w, y, w, bar_h, True)}' fill='{colour}'/>"
            f"<text class='val' x='{label_w + w + 6:.1f}' y='{y + bar_h * .72:.1f}'>{escape(fmt(value))}</text></g>")
    if reference:
        x = label_w + scale(reference[0])
        parts.insert(1, f"<line x1='{x:.1f}' x2='{x:.1f}' y1='{top - 6}' y2='{height - 20}' stroke='var(--ink2)' "
                        f"stroke-width='1.5'/><text class='tick' x='{x:.1f}' y='{top - 10}' text-anchor='middle'>"
                        f"{escape(reference[1])} {escape(fmt(reference[0]))}</text>")
    parts.append(f"<line class='axis' x1='{label_w}' x2='{label_w}' y1='{top - 4}' y2='{height - 20}'/></svg>")
    legend = ""
    if highlight:
        legend = _legend([("Highlighted in text", SLOTS[1], "dot"), ("Other groups", SLOTS[0], "dot")])
    return _figure(title, subtitle, "".join(parts), ["Group", value_label],
                   [[label, fmt(value)] for label, value, _ in rows], legend)


def lines(title: str, subtitle: str, x_labels: list[str], series: list[tuple[str, list[float | None]]],
          fmt, y_from_zero: bool = True) -> str:
    """Line chart, one shared y axis, up to three series, crosshair-band tooltips."""
    width, height = 900, 300
    left, right, top, bottom = 56, 70, 12, 34
    values = [v for _, vals in series for v in vals if v is not None]
    lo = 0.0 if y_from_zero else min(values) * 0.9
    hi = _nice_max(max(values) * 1.08)
    ticks = _ticks(lo, hi, 5)
    lo, hi = ticks[0], ticks[-1]
    plot_w, plot_h = width - left - right, height - top - bottom
    step = plot_w / max(len(x_labels) - 1, 1)
    xs = [left + i * step for i in range(len(x_labels))]
    y_of = lambda v: top + plot_h * (1 - (v - lo) / (hi - lo))
    parts = [f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>"]
    for tick in ticks:
        y = y_of(tick)
        parts.append(f"<line class='grid' x1='{left}' x2='{left + plot_w}' y1='{y:.1f}' y2='{y:.1f}'/>"
                     f"<text class='tick' x='{left - 8}' y='{y + 4:.1f}' text-anchor='end'>{escape(fmt(tick))}</text>")
    every = max(1, math.ceil(len(x_labels) / 8))
    last = len(x_labels) - 1
    shown = {i for i in range(0, len(x_labels), every)}
    if last not in shown:
        shown = {i for i in shown if last - i >= every / 2 + 0.5} | {last}
    for i, label in enumerate(x_labels):
        if i in shown:
            parts.append(f"<text class='tick' x='{xs[i]:.1f}' y='{height - 12}' text-anchor='middle'>{escape(label)}</text>")
    placed: list[float] = []
    for s_index, (name, vals) in enumerate(series):
        colour = SLOTS[s_index]
        pts = [(xs[i], y_of(v)) for i, v in enumerate(vals) if v is not None]
        path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f"<path d='{path}' fill='none' stroke='{colour}' stroke-width='2' stroke-linejoin='round' stroke-linecap='round'/>")
        x_end, y_end = pts[-1]
        parts.append(f"<circle cx='{x_end:.1f}' cy='{y_end:.1f}' r='4' fill='{colour}' stroke='var(--surface)' stroke-width='2'/>")
        # End labels only where they do not collide; the legend and tooltip carry the rest.
        if all(abs(y_end - other) >= 14 for other in placed):
            placed.append(y_end)
            parts.append(f"<text class='val' x='{x_end + 8:.1f}' y='{y_end + 4:.1f}'>{escape(fmt(vals[-1]))}</text>")
    for i, label in enumerate(x_labels):
        tip = label + "\n" + "\n".join(f"{name}: {fmt(vals[i]) if vals[i] is not None else 'n/a'}" for name, vals in series)
        x0 = xs[i] - step / 2 if i else xs[i]
        w = step if 0 < i < len(x_labels) - 1 else step / 2
        parts.append(f"<g data-tip='{escape(tip)}'><rect class='mark' x='{x0:.1f}' y='{top}' width='{max(w, 6):.1f}' "
                     f"height='{plot_h}' fill='transparent'/></g>")
    parts.append(f"<line class='axis' x1='{left}' x2='{left + plot_w}' y1='{top + plot_h}' y2='{top + plot_h}'/></svg>")
    legend = _legend([(name, SLOTS[i], "") for i, (name, _) in enumerate(series)]) if len(series) > 1 else ""
    rows = [[label] + [fmt(vals[i]) if vals[i] is not None else "n/a" for _, vals in series] for i, label in enumerate(x_labels)]
    return _figure(title, subtitle, "".join(parts), ["Period"] + [n for n, _ in series], rows, legend)


def columns(title: str, subtitle: str, categories: list[str], series: list[tuple[str, list[float]]], fmt) -> str:
    """Grouped columns (up to three series) on one baseline."""
    width, height = 900, 260
    left, right, top, bottom = 48, 16, 20, 34
    hi = _nice_max(max(v for _, vals in series for v in vals) * 1.1)
    ticks = _ticks(0, hi, 4)
    hi = ticks[-1]
    plot_w, plot_h = width - left - right, height - top - bottom
    band = plot_w / len(categories)
    bar_w = min(24, (band - 10) / len(series) - 2)
    y_of = lambda v: top + plot_h * (1 - v / hi)
    parts = [f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>"]
    for tick in ticks:
        y = y_of(tick)
        parts.append(f"<line class='grid' x1='{left}' x2='{left + plot_w}' y1='{y:.1f}' y2='{y:.1f}'/>"
                     f"<text class='tick' x='{left - 8}' y='{y + 4:.1f}' text-anchor='end'>{escape(fmt(tick))}</text>")
    for i, cat in enumerate(categories):
        cx = left + band * i + band / 2
        group_w = len(series) * bar_w + (len(series) - 1) * 2
        tip = cat + "\n" + "\n".join(f"{name}: {fmt(vals[i])}" for name, vals in series)
        parts.append(f"<g data-tip='{escape(tip)}'><rect x='{cx - band / 2:.1f}' y='{top}' width='{band:.1f}' height='{plot_h}' fill='transparent'/>")
        for s_index, (_, vals) in enumerate(series):
            x = cx - group_w / 2 + s_index * (bar_w + 2)
            h = max(plot_h * vals[i] / hi, 1.5)
            parts.append(f"<path class='mark' d='{_rounded_bar(x, top + plot_h - h, bar_w, h, False)}' fill='{SLOTS[s_index]}'/>")
            if len(categories) <= 6:
                parts.append(f"<text class='val' x='{x + bar_w / 2:.1f}' y='{top + plot_h - h - 6:.1f}' text-anchor='middle'>"
                             f"{escape(fmt(vals[i]))}</text>")
        parts.append(f"</g><text class='tick' x='{cx:.1f}' y='{height - 12}' text-anchor='middle'>{escape(cat)}</text>")
    parts.append(f"<line class='axis' x1='{left}' x2='{left + plot_w}' y1='{top + plot_h}' y2='{top + plot_h}'/></svg>")
    legend = _legend([(name, SLOTS[i], "dot") for i, (name, _) in enumerate(series)]) if len(series) > 1 else ""
    rows = [[cat] + [fmt(vals[i]) for _, vals in series] for i, cat in enumerate(categories)]
    return _figure(title, subtitle, "".join(parts), ["Category"] + [n for n, _ in series], rows, legend)


def funnel(title: str, subtitle: str, points: list[dict], p0: float, limits, fmt_p, fmt_n,
           x_label: str = "Volume (log scale)") -> str:
    """Funnel plot of proportions against volume (log x axis).

    ``points``: dicts with n, p, label, flag in {"above", "below", None}.
    ``limits(n, z)`` returns the (lower, upper) control limits at volume n; they
    need not be symmetric (limits from a transformed scale usually are not).
    """
    width, height = 900, 360
    left, right, top, bottom = 56, 20, 14, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    n_lo = 10 ** math.floor(math.log10(min(p["n"] for p in points)))
    n_hi = 10 ** math.ceil(math.log10(max(p["n"] for p in points)))
    p_vals = [p["p"] for p in points]
    p_hi = _nice_max(max(p_vals) * 1.05)
    ticks = _ticks(0, p_hi, 5)
    p_hi = ticks[-1]
    x_of = lambda n: left + plot_w * (math.log10(n) - math.log10(n_lo)) / (math.log10(n_hi) - math.log10(n_lo))
    y_of = lambda p: top + plot_h * (1 - p / p_hi)
    parts = [f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>"]
    for tick in ticks:
        y = y_of(tick)
        parts.append(f"<line class='grid' x1='{left}' x2='{left + plot_w}' y1='{y:.1f}' y2='{y:.1f}'/>"
                     f"<text class='tick' x='{left - 8}' y='{y + 4:.1f}' text-anchor='end'>{escape(fmt_p(tick))}</text>")
    decade = n_lo
    while decade <= n_hi:
        x = x_of(decade)
        parts.append(f"<text class='tick' x='{x:.1f}' y='{height - 20}' text-anchor='middle'>{escape(fmt_n(decade))}</text>")
        decade *= 10
    parts.append(f"<text class='tick' x='{left + plot_w / 2:.1f}' y='{height - 4}' text-anchor='middle'>"
                 f"{escape(x_label)}</text>")
    samples = [n_lo * (n_hi / n_lo) ** (i / 120) for i in range(121)]
    for z, dash in ((1.96, "4 4"), (3.09, "0")):
        for side in (0, 1):
            pts = [(x_of(n), y_of(min(max(limits(n, z)[side], 0), p_hi))) for n in samples]
            d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            parts.append(f"<path d='{d}' fill='none' stroke='var(--ink2)' stroke-width='1' stroke-dasharray='{dash}' opacity='.8'/>")
    y0 = y_of(p0)
    parts.append(f"<line x1='{left}' x2='{left + plot_w}' y1='{y0:.1f}' y2='{y0:.1f}' stroke='var(--ink2)' stroke-width='1.5'/>"
                 f"<text class='tick' x='{left + 4}' y='{y0 - 5:.1f}'>England {escape(fmt_p(p0))}</text>")
    for p in sorted(points, key=lambda q: q["flag"] is not None):
        x, y = x_of(p["n"]), y_of(p["p"])
        if p["flag"] == "above":
            mark = f"<circle class='mark' cx='{x:.1f}' cy='{y:.1f}' r='4.5' fill='var(--s2)' stroke='var(--surface)' stroke-width='2'/>"
        elif p["flag"] == "below":
            mark = f"<circle class='mark' cx='{x:.1f}' cy='{y:.1f}' r='4' fill='var(--surface)' stroke='var(--s3)' stroke-width='2'/>"
        else:
            mark = f"<circle class='mark' cx='{x:.1f}' cy='{y:.1f}' r='4' fill='var(--s1)' stroke='var(--surface)' stroke-width='1.5' opacity='.75'/>"
        tip = f"{p['label']}\nDNA rate {fmt_p(p['p'])} of {fmt_n(p['n'])} appointments with a recorded outcome"
        parts.append(f"<g data-tip='{escape(tip)}'><circle cx='{x:.1f}' cy='{y:.1f}' r='10' fill='transparent'/>{mark}</g>")
    parts.append(f"<line class='axis' x1='{left}' x2='{left + plot_w}' y1='{top + plot_h}' y2='{top + plot_h}'/></svg>")
    legend = _legend([("Above the 99.8% limit", "var(--s2)", "dot"), ("Within limits", "var(--s1)", "dot"),
                      ("Below the 99.8% limit", "var(--s3)", "dot hollow"),
                      ("95% limit (dashed) and 99.8% limit (solid)", "var(--ink2)", "")])
    legend = legend.replace("dot hollow' style='background:var(--s3)'", "dot hollow' style='border-color:var(--s3)'")
    rows = [[p["label"], fmt_n(p["n"]), fmt_p(p["p"]), p["flag"] or "within"] for p in
            sorted(points, key=lambda q: -q["p"])]
    return _figure(title, subtitle, "".join(parts), ["Provider", "Appointments", "DNA rate", "Funnel position"], rows, legend)
