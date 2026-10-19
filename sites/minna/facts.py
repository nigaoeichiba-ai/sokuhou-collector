"""みんなのイラスト: facts that are computed from the pictures themselves.

Every picture page used to hold a title, a one-line description and the same stock text; Google AdSense judged another site of ours "low value" for that kind of page.
Here the page gets what only the picture can tell: its size and print size, how much of the canvas the drawing fills, its main colours, and on which background colours
it stays easy to see.  Everything is measured from the file (nothing is written by hand), so no two pictures say the same thing, and a set or a genre page can be
summed up from the same numbers.  The result of one picture is a small dict; the build keeps it next to the picture in the disk cache.
"""
from __future__ import annotations

import colorsys

# the background colours of the "background" buttons on a picture page (the names are the buttons' own)
BACKGROUNDS = [("白", (255, 255, 255)), ("黄", (255, 201, 60)), ("桃", (255, 214, 224)), ("空", (217, 241, 255)), ("黒", (43, 27, 20))]
LOW_CONTRAST = 1.6          # a WCAG-style contrast ratio under this: the drawing nearly melts into the background
SAMPLE = 96                 # the picture is looked at in a copy of at most this many pixels on a side


def _lin(c: int) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    return 0.2126 * _lin(rgb[0]) + 0.7152 * _lin(rgb[1]) + 0.0722 * _lin(rgb[2])


def contrast(a: float, b: float) -> float:
    hi, lo = (a, b) if a >= b else (b, a)
    return (hi + 0.05) / (lo + 0.05)


def color_name(rgb: tuple[int, int, int]) -> str:
    """A plain Japanese colour word for a pixel."""
    r, g, b = (v / 255 for v in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h *= 360
    if l < 0.14:
        return "黒"
    if l > 0.92 and s < 0.5 or (s < 0.10 and l > 0.85):
        return "白"
    if s < 0.12:
        return "灰色" if l > 0.28 else "黒"
    if h < 14 or h >= 346:
        return "桃色" if l > 0.72 else "赤"
    if h < 42:
        return "茶色" if l < 0.50 else ("肌色" if l > 0.78 else "橙")
    if h < 68:
        return "黄" if l > 0.45 else "黄土色"
    if h < 166:
        return "緑"
    if h < 200:
        return "水色"
    if h < 258:
        return "青"
    if h < 300:
        return "紫"
    return "桃色" if l > 0.55 else "赤紫"


def compute(path) -> dict:
    """The facts of one picture file (a transparent WebP of the library)."""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    small = im.copy()
    small.thumbnail((SAMPLE, SAMPLE), Image.BOX)
    raw = small.tobytes()
    px = [(raw[i], raw[i + 1], raw[i + 2], raw[i + 3]) for i in range(0, len(raw), 4)]
    opaque = [(r, g, b) for r, g, b, a in px if a >= 128]
    total = max(1, len(px))
    out = {"w": w, "h": h, "fill": round(100 * len(opaque) / total)}
    names: dict[str, int] = {}
    for rgb in opaque:
        n = color_name(rgb)
        names[n] = names.get(n, 0) + 1
    n_op = max(1, len(opaque))
    ranked = sorted(names.items(), key=lambda kv: (-kv[1], kv[0]))
    out["colors"] = [[n, round(100 * c / n_op)] for n, c in ranked if c / n_op >= 0.08][:3] or [[ranked[0][0], 100]] if ranked else []
    # what decides whether a drawing stays readable on a background is its outline: the opaque pixels that touch a transparent one
    sw, sh = small.size
    alpha = [a for _r, _g, _b, a in px]
    edge = []
    for y in range(sh):
        for x in range(sw):
            i = y * sw + x
            if alpha[i] < 128:
                continue
            if x in (0, sw - 1) or y in (0, sh - 1) or alpha[i - 1] < 128 or alpha[i + 1] < 128 or alpha[i - sw] < 128 or alpha[i + sw] < 128:
                edge.append(px[i][:3])
    lums = [luminance(p) for p in edge]
    n_edge = max(1, len(edge))
    out["bg_low"] = {name: round(100 * sum(1 for l in lums if contrast(l, luminance(bg)) < LOW_CONTRAST) / n_edge) for name, bg in BACKGROUNDS} if lums else {}
    out["dark"] = round(100 * sum(1 for l in lums if l < 0.03) / n_edge) if lums else 0     # the share of the outline that is near black
    return out


def shape(w: int, h: int) -> str:
    r = w / h
    if r >= 1.15:
        return "横長"
    if r <= 0.87:
        return "縦長"
    return "ほぼ正方形"


def mm(px: int, dpi: int) -> float:
    return px / dpi * 25.4


def bg_sentence(bg_low: dict[str, int]) -> str:
    """Which backgrounds keep the outline easy to see, from the measured share of the outline that is close in tone to each."""
    if not bg_low:
        return ""
    good = [n for n, v in bg_low.items() if v < 15]
    bad = [(n, v) for n, v in bg_low.items() if v >= 30]
    if not bad:
        return "輪郭は、白・黄・桃・空・黒のどの背景でも見分けられます。"
    lo, hi = min(v for _n, v in bad), max(v for _n, v in bad)
    share = f"{lo}%ほど" if lo == hi else f"{lo}〜{hi}%ほど"
    blur = "・".join(n for n, _v in bad) + f"の背景では、輪郭の{share}が背景に近い色で、縁がぼやけます。"
    return (("・".join(good) + "の背景ならはっきり見えます。") if good else "") + blur
