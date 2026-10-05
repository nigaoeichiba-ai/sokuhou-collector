"""Dependency-free inline SVG charts for the bear site: several lines on one axis, and plain bars.

Both start the vertical axis at 0 (counts), label the axis, and carry a title and description for screen readers.
"""
from __future__ import annotations

import html
import math


def nice_max(v: float) -> float:
    """Round a maximum up to 1, 2, 2.5, 5 or 10 times a power of ten, so the axis ticks are readable numbers."""
    if v <= 0:
        return 1
    exp = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def _ticks(top: float) -> list[float]:
    return [top * i / 4 for i in range(5)]


def _fmt(v: float) -> str:
    return f"{v:,.0f}" if v == int(v) else f"{v:,.1f}"


def lines(series: list[dict], x_labels: list[str], *, title: str, desc: str, uid: str = "c") -> str:
    """series: [{"label": str, "values": [float | None, ...], "cls": "c0".."c4"}]; None leaves a gap."""
    w, h, pl, pr, pt, pb = 720, 300, 56, 18, 18, 36
    top = nice_max(max((v for s in series for v in s["values"] if v is not None), default=1))
    n = len(x_labels)

    def x(i: int) -> float:
        return pl + (w - pl - pr) * i / (n - 1)

    def y(v: float) -> float:
        return pt + (h - pt - pb) * (1 - v / top)

    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{uid}t {uid}d" xmlns="http://www.w3.org/2000/svg">',
           f'<title id="{uid}t">{html.escape(title)}</title><desc id="{uid}d">{html.escape(desc)}</desc>']
    for t in _ticks(top):
        out.append(f'<line class="grid" x1="{pl}" y1="{y(t):.1f}" x2="{w - pr}" y2="{y(t):.1f}"/>'
                   f'<text x="{pl - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{_fmt(t)}</text>')
    out.append(f'<line class="axis" x1="{pl}" y1="{h - pb}" x2="{w - pr}" y2="{h - pb}"/>')
    for i, lab in enumerate(x_labels):
        out.append(f'<text x="{x(i):.1f}" y="{h - 14}" text-anchor="middle">{html.escape(lab)}</text>')
    for s in series:
        col = f"var(--{s['cls']})"
        runs: list[list[tuple[float, float]]] = [[]]
        for i, v in enumerate(s["values"]):
            if v is None:
                if runs[-1]:
                    runs.append([])
            else:
                runs[-1].append((x(i), y(v)))
        width = 3.2 if s.get("strong") else 2
        for run in runs:
            if len(run) > 1:
                pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in run)
                out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')
            for px, py in run:
                out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{3.6 if s.get("strong") else 2.6}" fill="{col}"/>')
    out.append("</svg>")
    legend = "".join(f'<span><i style="background:var(--{s["cls"]})"></i>{html.escape(s["label"])}</span>' for s in series)
    return f'<div class="chart-box">{"".join(out)}</div><div class="legend">{legend}</div>'


def bars(labels: list[str], values: list[float], *, title: str, desc: str, uid: str = "b", cls: str = "c3",
         marks: list[float] | None = None, marks_label: str = "") -> str:
    """Vertical bars; `marks` draws a second, narrower bar per label (e.g. deaths next to people injured)."""
    w, h, pl, pr, pt, pb = 720, 300, 56, 18, 18, 40
    top = nice_max(max(values + (marks or []), default=1))
    n = len(labels)
    slot = (w - pl - pr) / n

    def y(v: float) -> float:
        return pt + (h - pt - pb) * (1 - v / top)

    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{uid}t {uid}d" xmlns="http://www.w3.org/2000/svg">',
           f'<title id="{uid}t">{html.escape(title)}</title><desc id="{uid}d">{html.escape(desc)}</desc>']
    for t in _ticks(top):
        out.append(f'<line class="grid" x1="{pl}" y1="{y(t):.1f}" x2="{w - pr}" y2="{y(t):.1f}"/>'
                   f'<text x="{pl - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{_fmt(t)}</text>')
    out.append(f'<line class="axis" x1="{pl}" y1="{h - pb}" x2="{w - pr}" y2="{h - pb}"/>')
    for i, (lab, v) in enumerate(zip(labels, values)):
        bw = slot * (0.42 if marks else 0.62)
        x0 = pl + slot * i + (slot - (bw * 2 + 3 if marks else bw)) / 2
        out.append(f'<rect x="{x0:.1f}" y="{y(v):.1f}" width="{bw:.1f}" height="{max(0.0, h - pb - y(v)):.1f}" rx="2" fill="var(--{cls})"/>')
        if marks:
            mv = marks[i]
            out.append(f'<rect x="{x0 + bw + 3:.1f}" y="{y(mv):.1f}" width="{bw:.1f}" height="{max(0.0, h - pb - y(mv)):.1f}" rx="2" fill="var(--c4)"/>')
        if n <= 12 or i % 2 == 0 or i == n - 1:
            out.append(f'<text x="{pl + slot * (i + 0.5):.1f}" y="{h - 20}" text-anchor="middle">{html.escape(lab)}</text>')
    out.append("</svg>")
    legend = ""
    if marks:
        legend = (f'<div class="legend"><span><i style="background:var(--{cls})"></i>{html.escape(title.split("の")[0] or "件数")}</span>'
                  f'<span><i style="background:var(--c4)"></i>{html.escape(marks_label)}</span></div>')
    return f'<div class="chart-box">{"".join(out)}</div>{legend}'
