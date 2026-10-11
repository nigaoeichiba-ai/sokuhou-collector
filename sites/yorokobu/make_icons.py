"""Draws the site's icons (favicon, touch icon, 192/512) from the same geometry as the header logo mark in build.py (LOGO_MARK):
a white gift box on the accent coral.  Run once after the mark changes:  python -m sites.yorokobu.make_icons

Small sizes get a larger box inside the tile so it still reads in a browser tab; the touch icon is a full square (iOS rounds it itself).
"""
from __future__ import annotations

from pathlib import Path

CORAL, WHITE = (232, 80, 63), (255, 255, 255)
OUT = Path(__file__).resolve().parent / "assets"
S = 36                                   # the logo's viewBox


def _cubic(p0, p1, p2, p3, n=24):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return pts


def _bow(sign):
    """One loop of the bow, as a polygon (the SVG path 'M18 12c-3-5-8-4-6.5-1.5 1 1.6 4 1.5 6.5 1.5z', mirrored for the other side)."""
    s = sign
    a = (18, 12)
    p = [a] + _cubic(a, (18 - 3 * s, 7), (18 - 8 * s, 8), (18 - 6.5 * s, 10.5)) + _cubic((18 - 6.5 * s, 10.5), (18 - 5.5 * s, 12.1), (18 - 2.5 * s, 12), a)
    return p


def icon(px: int, *, rounded: bool = True, zoom: float = 1.0):
    from PIL import Image, ImageDraw
    big = 8                                                     # supersampling
    n = px * big
    k = n / S
    img = Image.new("RGB", (n, n), CORAL)                       # drawn opaque and given its rounded corners at the end (no dark fringe)
    d = ImageDraw.Draw(img)

    def tf(x, y):                                               # zoom around the centre of the drawing (18, 18.5)
        return ((18 + (x - 18) * zoom) * k, (18.5 + (y - 18.5) * zoom) * k)

    def rect(x, y, w, h, r, fill):
        (x0, y0), (x1, y1) = tf(x, y), tf(x + w, y + h)
        d.rounded_rectangle([x0, y0, x1, y1], radius=r * k * zoom, fill=fill)

    rect(8, 16, 20, 12, 1.5, WHITE)                             # body
    rect(6.5, 12, 23, 5, 1.5, WHITE)                            # lid
    rect(16.5, 12, 3, 16, 0, CORAL)                             # ribbon
    for sign in (1, -1):
        d.polygon([tf(x, y) for x, y in _bow(sign)], fill=WHITE)
    out = img.resize((px, px), Image.LANCZOS).convert("RGBA")
    if rounded:
        mask = Image.new("L", (n, n), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, n - 1, n - 1], radius=int(9 * k), fill=255)
        out.putalpha(mask.resize((px, px), Image.LANCZOS))
    return out


def main() -> None:
    icon(512).save(OUT / "icon-512.png")
    icon(192).save(OUT / "icon-192.png")
    icon(180, rounded=False).save(OUT / "apple-touch-icon.png")
    icon(32, zoom=1.18).save(OUT / "favicon-32.png")
    icon(48, zoom=1.12).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
