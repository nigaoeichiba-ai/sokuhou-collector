"""Tiny dependency-free inline SVG charts."""
from __future__ import annotations

import html


def line(items: list[tuple[str, float]], *, title: str, desc: str, unit: str = "円", label_every: int = 1) -> str:
    """A line chart with a non-zero baseline (the axis is not claimed to start at 0)."""
    if len(items) < 2:
        return ""
    w, h, pl, pr, pt, pb = 720, 280, 16, 16, 34, 40
    vals = [v for _, v in items]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    lo -= span * 0.08
    hi += span * 0.12
    n = len(items)

    def x(i: int) -> float:
        return pl + (w - pl - pr) * i / (n - 1)

    def y(v: float) -> float:
        return pt + (h - pt - pb) * (1 - (v - lo) / (hi - lo))

    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(items))
    area = f"{x(0):.1f},{h - pb} {pts} {x(n - 1):.1f},{h - pb}"
    parts = [
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="ct cd" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="ct">{html.escape(title)}</title><desc id="cd">{html.escape(desc)}</desc>',
        f'<line class="axis" x1="{pl}" y1="{h - pb}" x2="{w - pr}" y2="{h - pb}"/>',
        f'<polygon class="area" points="{area}"/>',
        f'<polyline class="stroke" points="{pts}"/>',
    ]
    for i, (label, v) in enumerate(items):
        cx, cy = x(i), y(v)
        last = i == n - 1
        parts.append(f'<circle class="dot{" last" if last else ""}" cx="{cx:.1f}" cy="{cy:.1f}" r="{5 if last else 3.2}"/>')
        if i % label_every == 0 or last:
            anchor = "end" if last else ("start" if i == 0 else "middle")
            parts.append(
                f'<text class="val{" last" if last else ""}" x="{cx:.1f}" y="{cy - 10:.1f}" text-anchor="{anchor}">{v:,.0f}{html.escape(unit)}</text>'
                f'<text class="lab" x="{cx:.1f}" y="{h - pb + 18}" text-anchor="{anchor}">{html.escape(label)}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _ticks(lo: float, hi: float) -> list[int]:
    """Round y-axis values inside the drawn range: multiples of 50, 100, 200, 250 or 500 (the first step that gives at most 6 lines)."""
    for step in (10, 20, 25, 50, 100, 200, 250, 500, 1000):
        first = -(-lo // step) * step
        ticks = [int(t) for t in range(int(first), int(hi) + 1, step)]
        if 2 <= len(ticks) <= 6:
            return ticks
    return [round(lo), round(hi)]


def compare(xs: list[str], series: list[dict], *, title: str, desc: str, unit: str = "円", label_every: int = 5) -> str:
    """Lines over the same x labels.  series: [{"name", "values" (None breaks the line), "cls" ("" or "s2")}].  The axis does not start at 0 (the page says so)."""
    n = len(xs)
    if n < 2:
        return ""
    w, h, pl, pr, pt, pb = 720, 300, 52, 16, 40, 40
    vals = [v for s in series for v in s["values"] if v is not None]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    lo, hi = lo - span * 0.05, hi + span * 0.08

    def x(i: int) -> float:
        return pl + (w - pl - pr) * i / (n - 1)

    def y(v: float) -> float:
        return pt + (h - pt - pb) * (1 - (v - lo) / (hi - lo))
    parts = [
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="ct cd" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="ct">{html.escape(title)}</title><desc id="cd">{html.escape(desc)}</desc>',
    ]
    for t in _ticks(lo, hi):
        parts.append(f'<line class="grid" x1="{pl}" y1="{y(t):.1f}" x2="{w - pr}" y2="{y(t):.1f}"/><text class="yl" x="{pl - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{t:,}</text>')
    parts.append(f'<line class="axis" x1="{pl}" y1="{h - pb}" x2="{w - pr}" y2="{h - pb}"/>')
    for k, s in enumerate(series):
        run: list[tuple[float, float]] = []
        runs = []
        for i, v in enumerate(s["values"]):
            if v is None:
                if run:
                    runs.append(run)
                run = []
            else:
                run.append((x(i), y(v)))
        if run:
            runs.append(run)
        for r in runs:
            if len(r) > 1:
                parts.append(f'<polyline class="stroke {s.get("cls", "")}" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in r)}"/>')
        last = max((i for i, v in enumerate(s["values"]) if v is not None), default=None)
        if last is not None:
            parts.append(f'<circle class="dot last {s.get("cls", "")}" cx="{x(last):.1f}" cy="{y(s["values"][last]):.1f}" r="4.5"/>'
                         f'<text class="val {s.get("cls", "")}" x="{x(last) - 8:.1f}" y="{y(s["values"][last]) - 9 - 14 * k:.1f}" text-anchor="end">{html.escape(s["name"])} {s["values"][last]:,.0f}{html.escape(unit)}</text>')
    for i, label in enumerate(xs):
        if (i % label_every == 0 and n - 1 - i >= max(2, label_every // 2)) or i == n - 1:
            anchor = "end" if i == n - 1 else ("start" if i == 0 else "middle")
            parts.append(f'<text class="lab" x="{x(i):.1f}" y="{h - pb + 18}" text-anchor="{anchor}">{html.escape(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def bars(items: list[tuple[str, float | None]], *, title: str, desc: str, unit: str = "円", label_every: int = 5) -> str:
    """Vertical bars from zero (None = no bar).  The largest bar and the last one carry their value."""
    n = len(items)
    vals = [v for _, v in items if v is not None]
    if n < 2 or not vals:
        return ""
    w, h, pl, pr, pt, pb = 720, 260, 40, 16, 34, 40
    top = max(vals) * 1.12 or 1
    slot = (w - pl - pr) / n

    def y(v: float) -> float:
        return pt + (h - pt - pb) * (1 - v / top)
    parts = [
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="ct cd" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="ct">{html.escape(title)}</title><desc id="cd">{html.escape(desc)}</desc>',
        f'<line class="grid" x1="{pl}" y1="{y(max(vals)):.1f}" x2="{w - pr}" y2="{y(max(vals)):.1f}"/><text class="yl" x="{pl - 6}" y="{y(max(vals)) + 4:.1f}" text-anchor="end">{max(vals):,.0f}</text>',
        f'<line class="axis" x1="{pl}" y1="{h - pb}" x2="{w - pr}" y2="{h - pb}"/><text class="yl" x="{pl - 6}" y="{h - pb + 4}" text-anchor="end">0</text>',
    ]
    biggest = max(range(n), key=lambda i: (items[i][1] if items[i][1] is not None else -1, i))
    for i, (label, v) in enumerate(items):
        cx = pl + slot * (i + 0.5)
        if v is not None and v > 0:
            parts.append(f'<rect class="bar{" hot" if i == biggest else ""}" x="{cx - slot * 0.36:.1f}" y="{y(v):.1f}" width="{slot * 0.72:.1f}" height="{h - pb - y(v):.1f}"/>')
        if v is not None and (i == biggest or (i == n - 1 and n - 1 - biggest > 3)):
            anchor = "end" if i == n - 1 else "middle"
            parts.append(f'<text class="val" x="{cx + (slot * 0.5 if i == n - 1 else 0):.1f}" y="{y(v) - 6:.1f}" text-anchor="{anchor}">{v:,.0f}{html.escape(unit)}</text>')
        if (i % label_every == 0 and n - 1 - i >= max(2, label_every // 2)) or i == n - 1:
            parts.append(f'<text class="lab" x="{cx:.1f}" y="{h - pb + 18}" text-anchor="{"end" if i == n - 1 else ("start" if i == 0 else "middle")}">{html.escape(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)
