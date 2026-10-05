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
